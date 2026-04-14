from datetime import datetime, timezone

from app.core.security import (
    build_totp_provisioning_uri,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp_code,
)


def test_password_hash_round_trip() -> None:
    stored_hash = hash_password("correct horse battery staple", salt=b"0123456789abcdef")

    assert verify_password("correct horse battery staple", stored_hash) is True
    assert verify_password("different password", stored_hash) is False


def test_totp_generation_and_verification() -> None:
    secret = generate_totp_secret()
    provisioning_uri = build_totp_provisioning_uri(email="user@example.com", secret=secret)

    assert provisioning_uri.startswith("otpauth://totp/")
    assert "user%40example.com" in provisioning_uri
    assert verify_totp_code(secret, "000000", timestamp=datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)) is False