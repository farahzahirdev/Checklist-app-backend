from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    build_totp_provisioning_uri,
    create_access_token,
    decrypt_secret,
    encrypt_secret,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp_code,
)
from app.models.audit_log import AuditAction, AuditLog
from app.models.mfa_totp import MfaTotp
from app.models.user import User, UserRole
from app.schemas.auth import AuthResponse, AuthUserResponse, MfaSetupDetailsResponse


def serialize_user(user: User) -> AuthUserResponse:
    return AuthUserResponse(id=user.id, email=user.email, role=user.role, is_active=bool(user.is_active))


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def _get_mfa_record(db: Session, user_id: UUID) -> MfaTotp | None:
    return db.scalar(select(MfaTotp).where(MfaTotp.user_id == user_id))


def _audit(db: Session, *, actor_user: User | None, action: AuditAction, target_entity: str, target_id: UUID | None = None) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user.id if actor_user else None,
            actor_role=actor_user.role if actor_user else None,
            action=action,
            target_entity=target_entity,
            target_id=target_id,
        )
    )


def register_user(db: Session, *, email: str, password: str) -> AuthResponse:
    existing_user = _get_user_by_email(db, email)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_already_registered")

    user = User(email=email.lower(), password_hash=hash_password(password), role=UserRole.customer)
    db.add(user)
    db.flush()

    token = create_access_token(user_id=str(user.id), role=user.role.value)
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=False, mfa_enabled=False)


def authenticate_user(db: Session, *, email: str, password: str, mfa_code: str | None = None) -> AuthResponse:
    user = _get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    try:
        password_is_valid = verify_password(password, user.password_hash)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials") from exc

    if not password_is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    mfa_record = _get_mfa_record(db, user.id)
    mfa_enabled = bool(mfa_record and mfa_record.is_verified)
    
    # CHANGE: MFA is now OPTIONAL during login
    # - If MFA is enabled and mfa_code is provided, verify it
    # - If MFA is enabled but no mfa_code provided, allow login (mfa_enabled will be True in response)
    # - This allows users to login and setup/verify MFA code later via the /mfa/verify endpoint
    if mfa_enabled and mfa_code:
        secret = decrypt_secret(mfa_record.secret_encrypted)
        if not verify_totp_code(secret, mfa_code):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_mfa_code")

    # CHANGE: Payment is now OPTIONAL for login
    # - No payment verification is performed during login
    # - Users can access the system without an active payment status
    # - Payment requirements will be enforced at resource access level if needed
    
    token = create_access_token(user_id=str(user.id), role=user.role.value)
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()

    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=False, mfa_enabled=mfa_enabled)


def start_mfa_enrollment(db: Session, *, user: User) -> MfaSetupDetailsResponse:
    secret = generate_totp_secret()
    encrypted_secret = encrypt_secret(secret)
    record = _get_mfa_record(db, user.id)
    if record is None:
        record = MfaTotp(user_id=user.id, secret_encrypted=encrypted_secret, is_verified=False)
        db.add(record)
    else:
        record.secret_encrypted = encrypted_secret
        record.is_verified = False

    db.commit()
    db.refresh(record)

    return MfaSetupDetailsResponse(
        secret=secret,
        provisioning_uri=build_totp_provisioning_uri(email=user.email, secret=secret),
        verified=False,
    )


def confirm_mfa_enrollment(db: Session, *, user: User, code: str) -> AuthResponse:
    record = _get_mfa_record(db, user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mfa_not_initialized")

    secret = decrypt_secret(record.secret_encrypted)
    if not verify_totp_code(secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_mfa_code")

    record.is_verified = True
    db.commit()

    token = create_access_token(user_id=str(user.id), role=user.role.value)
    _audit(db, actor_user=user, action=AuditAction.auth_mfa_verify, target_entity="user", target_id=user.id)
    db.commit()

    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=False, mfa_enabled=True)


def update_user_role(db: Session, *, actor_user: User, user_id: UUID, role: UserRole) -> AuthResponse:
    if actor_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_permissions")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    user.role = role
    _audit(db, actor_user=actor_user, action=AuditAction.user_role_change, target_entity="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return AuthResponse(user=serialize_user(user), mfa_required=False, mfa_enabled=bool(_get_mfa_record(db, user.id)))