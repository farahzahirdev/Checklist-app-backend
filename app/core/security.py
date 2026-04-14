from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import struct
from datetime import datetime, timezone
from typing import Final
from urllib.parse import quote

from fastapi import HTTPException, status

from app.core.config import get_settings

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover
    Fernet = None
    InvalidToken = Exception

PASSWORD_ALGORITHM: Final = "pbkdf2_sha256"
PASSWORD_ITERATIONS: Final = 310_000
PASSWORD_SALT_BYTES: Final = 16
TOTP_DIGITS: Final = 6
TOTP_PERIOD: Final = 30
TOTP_SECRET_BYTES: Final = 20


def _auth_secret_bytes() -> bytes:
    settings = get_settings()
    if not settings.auth_secret_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="auth_secret_key_missing")
    return settings.auth_secret_key.encode("utf-8")


def _auth_fernet() -> Fernet:
    if Fernet is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="cryptography_package_not_installed")

    key_material = hashlib.sha256(_auth_secret_bytes()).digest()
    return Fernet(base64.urlsafe_b64encode(key_material))


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = PASSWORD_ITERATIONS) -> str:
    if not password:
        raise ValueError("password must not be empty")

    salt_bytes = salt or secrets.token_bytes(PASSWORD_SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)

    encoded_salt = base64.b64encode(salt_bytes).decode("ascii")
    encoded_key = base64.b64encode(derived_key).decode("ascii")
    return f"{PASSWORD_ALGORITHM}${iterations}${encoded_salt}${encoded_key}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iteration_text, encoded_salt, encoded_key = stored_hash.split("$")
    except ValueError as exc:
        raise ValueError("stored_hash is not in the expected format") from exc

    if algorithm != PASSWORD_ALGORITHM:
        raise ValueError(f"unsupported password algorithm: {algorithm}")

    iterations = int(iteration_text)
    salt_bytes = base64.b64decode(encoded_salt)
    expected_key = base64.b64decode(encoded_key)
    actual_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return hmac.compare_digest(actual_key, expected_key)


def generate_totp_secret() -> str:
    secret_bytes = secrets.token_bytes(TOTP_SECRET_BYTES)
    return base64.b32encode(secret_bytes).decode("ascii").rstrip("=")


def build_totp_provisioning_uri(*, email: str, secret: str, issuer: str = "Checklist App") -> str:
    label = quote(f"{issuer}:{email}")
    issuer_value = quote(issuer)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer_value}&digits={TOTP_DIGITS}&period={TOTP_PERIOD}"


def _decode_totp_secret(secret: str) -> bytes:
    normalized_secret = secret.strip().replace(" ", "").upper()
    padding = "=" * (-len(normalized_secret) % 8)
    return base64.b32decode(f"{normalized_secret}{padding}", casefold=True)


def _totp_counter(timestamp: int, period: int) -> int:
    return timestamp // period


def _hotp(secret_bytes: bytes, counter: int, digits: int) -> str:
    counter_bytes = struct.pack(">Q", counter)
    digest = hmac.new(secret_bytes, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary_code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    code = binary_code % (10 ** digits)
    return f"{code:0{digits}d}"


def verify_totp_code(
    secret: str,
    code: str,
    *,
    timestamp: datetime | None = None,
    period: int = TOTP_PERIOD,
    digits: int = TOTP_DIGITS,
    window: int = 1,
) -> bool:
    if not code.isdigit() or len(code) != digits:
        return False

    moment = timestamp or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    current_timestamp = int(moment.astimezone(timezone.utc).timestamp())
    secret_bytes = _decode_totp_secret(secret)
    current_counter = _totp_counter(current_timestamp, period)

    for delta in range(-window, window + 1):
        if _hotp(secret_bytes, current_counter + delta, digits) == code:
            return True

    return False


def encrypt_secret(value: str) -> str:
    return _auth_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _auth_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_encrypted_secret") from exc


def create_signed_token(payload: dict[str, object], *, ttl_minutes: int, token_type: str = "access") -> str:
    settings = get_settings()
    issued_at = datetime.now(timezone.utc)
    claims = {
        **payload,
        "typ": token_type,
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp() + ttl_minutes * 60),
    }
    body = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8")
    encoded_body = base64.urlsafe_b64encode(body).rstrip(b"=")
    signature = hmac.new(settings.auth_secret_key.encode("utf-8"), encoded_body, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return f"{encoded_body.decode('ascii')}.{encoded_signature.decode('ascii')}"


def verify_signed_token(token: str, *, token_type: str = "access") -> dict[str, object]:
    settings = get_settings()
    try:
        encoded_body, encoded_signature = token.split(".", 1)
        expected_signature = hmac.new(
            settings.auth_secret_key.encode("utf-8"), encoded_body.encode("ascii"), hashlib.sha256
        ).digest()
        actual_signature = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected_signature, actual_signature):
            raise ValueError("invalid signature")

        body = base64.urlsafe_b64decode(encoded_body + "=" * (-len(encoded_body) % 4))
        claims = json.loads(body.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc

    if claims.get("typ") != token_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_type")

    exp = claims.get("exp")
    if not isinstance(exp, int) or datetime.now(timezone.utc).timestamp() >= exp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_expired")

    return claims


def create_access_token(*, user_id: str, role: str, ttl_minutes: int | None = None) -> str:
    settings = get_settings()
    return create_signed_token(
        {"sub": user_id, "role": role},
        ttl_minutes=ttl_minutes or settings.auth_token_ttl_minutes,
        token_type="access",
    )