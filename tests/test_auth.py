from __future__ import annotations

import base64
import hashlib
import hmac
import struct
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
    verify_signed_token,
    verify_totp_code,
)
from app.models.audit_log import AuditLog
from app.models.mfa_totp import MfaTotp
from app.models.user import User, UserRole
from app.services.auth import authenticate_user, confirm_mfa_enrollment, register_user, start_mfa_enrollment, update_user_role


def _totp_code(secret: str, moment: datetime | None = None, digits: int = 6, period: int = 30) -> str:
    timestamp = int((moment or datetime.now(timezone.utc)).astimezone(timezone.utc).timestamp())
    normalized_secret = secret.strip().replace(" ", "").upper()
    padding = "=" * (-len(normalized_secret) % 8)
    secret_bytes = base64.b32decode(f"{normalized_secret}{padding}", casefold=True)
    counter = timestamp // period
    digest = hmac.new(secret_bytes, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary_code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{binary_code % (10 ** digits):0{digits}d}"


class FakeSession:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.mfa_records: list[MfaTotp] = []
        self.audit_logs: list[AuditLog] = []

    def add(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if isinstance(obj, User):
            if obj.is_active is None:
                obj.is_active = True
            self.users.append(obj)
        elif isinstance(obj, MfaTotp):
            if obj.is_verified is None:
                obj.is_verified = False
            self.mfa_records.append(obj)
        elif isinstance(obj, AuditLog):
            self.audit_logs.append(obj)

    def flush(self) -> None:
        for collection in (self.users, self.mfa_records, self.audit_logs):
            for obj in collection:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid4()

    def commit(self) -> None:
        return None

    def refresh(self, obj) -> None:
        return None

    def get(self, model, object_id):
        if model is User:
            return next((item for item in self.users if item.id == object_id), None)
        if model is MfaTotp:
            return next((item for item in self.mfa_records if item.user_id == object_id), None)
        return None

    def scalar(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        params = statement.compile().params
        if entity is User:
            email = next((value for key, value in params.items() if "email" in key), None)
            if email is None:
                return None
            return next((item for item in self.users if item.email == email.lower()), None)
        if entity is MfaTotp:
            user_id = next((value for key, value in params.items() if "user_id" in key), None)
            if user_id is None:
                return None
            if isinstance(user_id, str):
                user_id = UUID(user_id)
            return next((item for item in self.mfa_records if item.user_id == user_id), None)
        return None


def test_password_hash_round_trip() -> None:
    hashed = hash_password("strong-password-123")

    assert verify_password("strong-password-123", hashed)
    assert not verify_password("wrong-password", hashed)


def test_signed_token_round_trip() -> None:
    token = create_access_token(user_id=str(uuid4()), role=UserRole.customer.value, ttl_minutes=5)
    claims = verify_signed_token(token)

    assert claims["role"] == UserRole.customer.value
    assert claims["sub"]


def test_register_login_and_mfa_flow() -> None:
    db = FakeSession()

    registered = register_user(db, email="user@example.com", password="strong-password-123")
    assert registered.user.email == "user@example.com"
    assert registered.access_token is not None

    login_result = authenticate_user(db, email="user@example.com", password="strong-password-123")
    assert login_result.access_token is not None
    assert login_result.mfa_required is False

    user = db.users[0]
    setup_result = start_mfa_enrollment(db, user=user)
    code = _totp_code(setup_result.secret)
    assert verify_totp_code(setup_result.secret, code)

    verified_result = confirm_mfa_enrollment(db, user=user, code=code)
    assert verified_result.mfa_enabled is True
    assert verified_result.access_token is not None

    mfa_login = authenticate_user(db, email="user@example.com", password="strong-password-123", mfa_code=code)
    assert mfa_login.access_token is not None
    assert mfa_login.mfa_enabled is True


def test_mfa_challenge_requires_code() -> None:
    db = FakeSession()
    user = User(email="mfa@example.com", password_hash=hash_password("strong-password-123"), role=UserRole.customer)
    db.add(user)
    db.flush()

    setup_result = start_mfa_enrollment(db, user=user)
    code = _totp_code(setup_result.secret)
    confirm_mfa_enrollment(db, user=user, code=code)

    challenged = authenticate_user(db, email="mfa@example.com", password="strong-password-123")
    assert challenged.mfa_required is True
    assert challenged.access_token is None


def test_admin_role_update() -> None:
    db = FakeSession()
    admin = User(email="admin@example.com", password_hash=hash_password("strong-password-123"), role=UserRole.admin)
    customer = User(email="customer@example.com", password_hash=hash_password("strong-password-123"), role=UserRole.customer)
    db.add(admin)
    db.add(customer)
    db.flush()

    updated = update_user_role(db, actor_user=admin, user_id=customer.id, role=UserRole.auditor)

    assert updated.user.role == UserRole.auditor
    assert db.users[1].role == UserRole.auditor
