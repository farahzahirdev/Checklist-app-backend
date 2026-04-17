from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    build_totp_provisioning_uri,
    create_access_token,
    create_mfa_challenge_token,
    decrypt_secret,
    encrypt_secret,
    generate_totp_secret,
    hash_password,
    verify_signed_token,
    verify_password,
    verify_totp_code,
)
from app.models.audit_log import AuditAction, AuditLog
from app.models.mfa_totp import MfaTotp
from app.models.user import User, UserRole
from app.schemas.auth import AuthResponse, AuthUserResponse, MfaSetupDetailsResponse, UserRoleCode
from app.services.rbac import RBACService
from app.services.user_management import UserManagementService


def _role_to_code(role: UserRole | str) -> UserRoleCode:
    role_name = role.value if isinstance(role, UserRole) else str(role)
    try:
        return UserRoleCode[role_name]
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="invalid_user_role") from exc


def _code_to_role(role_code: UserRoleCode) -> str:
    return role_code.name


def serialize_user(user: User) -> AuthUserResponse:
    if user.role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="user_role_missing")
    return AuthUserResponse(id=user.id, email=user.email, role=_role_to_code(user.role), is_active=bool(user.is_active))


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def _get_mfa_record(db: Session, user_id: UUID) -> MfaTotp | None:
    return db.scalar(select(MfaTotp).where(MfaTotp.user_id == user_id))


def _audit(db: Session, *, actor_user: User | None, action: AuditAction, target_entity: str, target_id: UUID | None = None) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user.id if actor_user else None,
            actor_role=(str(actor_user.role) if actor_user and actor_user.role else None),
            action=action,
            target_entity=target_entity,
            target_id=target_id,
        )
    )


def register_user(db: Session, *, email: str, password: str) -> AuthResponse:
    existing_user = _get_user_by_email(db, email)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email_already_registered")

    # Use UserManagementService to create user with default customer role and auto-assigned permissions
    user = UserManagementService.create_user_with_role(
        db,
        email=email.lower(),
        password_hash=hash_password(password),
        role_code="customer"
    )

    token = create_access_token(user_id=str(user.id), role=str(user.role))
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    # At registration, MFA is never enabled or required
    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=True, mfa_enabled=False)


def authenticate_user(db: Session, *, email: str, password: str) -> AuthResponse:
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

    # For customer users, show both true if MFA is enabled
    if str(user.role) == UserRole.customer.value:
        if mfa_enabled:
            challenge_token = create_mfa_challenge_token(user_id=str(user.id), role=str(user.role))
            return AuthResponse(
                user=serialize_user(user),
                access_token=None,
                challenge_token=challenge_token,
                mfa_required=True,
                mfa_enabled=True,
            )
        else:
            token = create_access_token(user_id=str(user.id), role=str(user.role))
            _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
            db.commit()
            return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=False, mfa_enabled=False)
    # For other users, keep existing logic
    if mfa_enabled:
        challenge_token = create_mfa_challenge_token(user_id=str(user.id), role=str(user.role))
        return AuthResponse(
            user=serialize_user(user),
            access_token=None,
            challenge_token=challenge_token,
            mfa_required=True,
            mfa_enabled=True,
        )
    token = create_access_token(user_id=str(user.id), role=str(user.role))
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()
    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=True, mfa_enabled=False)


def verify_mfa_challenge(db: Session, *, challenge_token: str, code: str) -> AuthResponse:
    claims = verify_signed_token(challenge_token, token_type="mfa_challenge")
    try:
        user_id = UUID(str(claims.get("sub", "")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_subject") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    mfa_record = _get_mfa_record(db, user.id)
    if mfa_record is None or not mfa_record.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mfa_not_enabled")

    secret = decrypt_secret(mfa_record.secret_encrypted)
    if not verify_totp_code(secret, code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_mfa_code")

    token = create_access_token(user_id=str(user.id), role=str(user.role))
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()

    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=False, mfa_enabled=True)


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


    provisioning_uri = build_totp_provisioning_uri(email=user.email, secret=secret)
    # Generate SVG QR code using qrcode
    import qrcode
    import qrcode.image.svg
    import io
    factory = qrcode.image.svg.SvgImage
    qr = qrcode.make(provisioning_uri, image_factory=factory)
    buf = io.BytesIO()
    qr.save(buf)
    import base64
    svg_qr = buf.getvalue().decode("utf-8")
    svg_b64 = base64.b64encode(svg_qr.encode("utf-8")).decode("ascii")
    svg_data_url = f"data:image/svg+xml;base64,{svg_b64}"

    return MfaSetupDetailsResponse(
        secret=secret,
        provisioning_uri=provisioning_uri,
        svg_qr=svg_data_url,
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

    token = create_access_token(user_id=str(user.id), role=str(user.role))
    _audit(db, actor_user=user, action=AuditAction.auth_mfa_verify, target_entity="user", target_id=user.id)
    db.commit()

    return AuthResponse(user=serialize_user(user), access_token=token, mfa_required=False, mfa_enabled=True)


def update_user_role(db: Session, *, actor_user: User, user_id: UUID, role_code: UserRoleCode) -> AuthResponse:
    if actor_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_permissions")

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    user.role = _code_to_role(role_code)
    _audit(db, actor_user=actor_user, action=AuditAction.user_role_change, target_entity="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return AuthResponse(user=serialize_user(user), mfa_required=False, mfa_enabled=bool(_get_mfa_record(db, user.id)))