from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
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
from app.core.config import get_settings
from app.models.audit_log import AuditAction, AuditLog
from app.models.mfa_totp import MfaTotp
from app.models.password_reset import PasswordResetToken
from app.models.company import Company
from app.models.user import User, UserRole
from app.schemas.auth import AuthResponse, AuthUserResponse, MfaSetupDetailsResponse, UserRoleCode
from app.services.rbac import RBACService
from app.services.user_management import UserManagementService
from app.services.settings_manager import get_runtime_int
import re
from app.utils.i18n_messages import translate


def _role_to_code(role: UserRole | str) -> UserRoleCode:
    role_name = role.value if isinstance(role, UserRole) else str(role)
    try:
        return UserRoleCode[role_name]
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="invalid_user_role") from exc


def _code_to_role(role_code: UserRoleCode) -> str:
    return role_code.name


def serialize_user(user: User, db: Session | None = None) -> AuthUserResponse:
    if user.role is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="user_role_missing")

    company_data: dict[str, str | None] = {
        "company_name": None,
        "company_slug": None,
        "company_industry": None,
        "company_size": None,
        "company_region": None,
        "company_email": None,
        "company_website": None,
        "company_country": None,
        "company_description": None,
    }

    if db is not None and user.primary_company_id not in (None, ""):
        company_id = user.primary_company_id
        company = None
        try:
            company = db.scalar(select(Company).where(Company.id == UUID(str(company_id))))
        except ValueError:
            company = None

        if company is not None:
            company_data.update(
                {
                    "company_name": company.name,
                    "company_slug": company.slug,
                    "company_industry": company.industry,
                    "company_size": company.size,
                    "company_region": company.region,
                    "company_email": company.email,
                    "company_website": company.website,
                    "company_country": company.country,
                    "company_description": company.description,
                }
            )

    return AuthUserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        username=user.username,
        role=_role_to_code(user.role),
        is_active=bool(user.is_active),
        email_verified=bool(user.email_verified),
        mfa_required=bool(user.mfa_required),
        preferred_language=(user.preferred_language or "en"),
        primary_company_id=user.primary_company_id,
        job_title=user.job_title,
        department=user.department,
        **company_data,
    )


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def _get_mfa_record(db: Session, user_id: UUID) -> MfaTotp | None:
    return db.scalar(select(MfaTotp).where(MfaTotp.user_id == user_id))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_reset_token(token: str) -> str:
    return _hash_token(token)


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


def get_password_validation_error(password: str) -> str | None:
    if len(password) < 8:
        return "password_too_short"
    if not re.search(r"[A-Z]", password):
        return "missing_uppercase"
    if not re.search(r"[a-z]", password):
        return "missing_lowercase"
    if not re.search(r"[0-9]", password):
        return "missing_digit"
    return None


def is_strong_password(password: str) -> bool:
    return get_password_validation_error(password) is None


def register_user(
    db: Session,
    *,
    email: str,
    password: str,
    full_name: str | None = None,
    username: str | None = None,
    company_name: str,
    job_title: str | None = None,
    department: str | None = None,
    company_industry: str | None = None,
    company_size: str | None = None,
    company_region: str | None = None,
    lang_code: str = "en"
) -> AuthResponse:
    """
    Register a new customer user with optional profile and company information.
    
    Args:
        db: Database session
        email: User email (required)
        password: User password (required, must be strong)
        full_name: User's full name (optional)
        username: Unique username (optional)
        company_name: User's company or organization name (required)
        job_title: User's job title (optional)
        department: User's department (optional)
        company_industry: Company industry classification (optional)
        company_size: Company size (optional)
        company_region: Geographic region (optional)
        lang_code: Language code for error messages
    
    Returns:
        AuthResponse with user and access token
    """
    from app.models.company import Company, UserCompanyAssignment

    if not (email or "").strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="email_missing")

    trimmed_company_name = (company_name or "").strip()
    if not trimmed_company_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="company_name_required")
    company_name = trimmed_company_name

    validation_error = get_password_validation_error(password)
    if validation_error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)
    
    existing_user = _get_user_by_email(db, email)
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=translate("email_already_registered", lang_code))
    
    # Check username uniqueness if provided
    if username:
        existing_username = db.query(User).filter(User.username == username.lower()).first()
        if existing_username:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("username_already_taken", lang_code))
    
    normalized_pref_lang = (lang_code or "en").strip().lower()
    if normalized_pref_lang == "cz":
        normalized_pref_lang = "cs"
    if normalized_pref_lang not in {"en", "cs"}:
        normalized_pref_lang = "en"

    # Create user with optional profile info
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        role=UserRole.customer.value,
        is_active=True,
        full_name=full_name,
        username=username.lower() if username else None,
        preferred_language=normalized_pref_lang,
    )
    db.add(user)
    db.flush()
    
    # Assign default customer permissions via RBAC
    RBACService.assign_role_by_code(db, user.id, "customer", user.id)
    
    # Create or link to company (organization name is required at registration)
    slug = company_name.lower().replace(" ", "-").replace("_", "-")
    slug = "".join(c for c in slug if c.isalnum() or c == "-")

    existing_company = db.query(Company).filter(Company.slug == slug).first()

    if existing_company:
        company = existing_company
    else:
        company = Company(
            name=company_name,
            slug=slug,
            industry=company_industry,
            size=company_size,
            region=company_region,
            is_active=True,
        )
        db.add(company)
        db.flush()

    user.primary_company_id = str(company.id)
    user.job_title = job_title
    user.department = department

    assignment = UserCompanyAssignment(
        user_id=user.id,
        company_id=company.id,
        role="owner" if not existing_company else "staff",
        job_title=job_title,
        department=department,
        is_active=True,
    )
    db.add(assignment)
    
    db.commit()
    db.refresh(user)
    
    settings = get_settings()
    auth_ttl = get_runtime_int(db, "auth_token_ttl_minutes", settings.auth_token_ttl_minutes)
    token = create_access_token(user_id=str(user.id), role=str(user.role), ttl_minutes=auth_ttl)
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()

    try:
        from app.services.notifications import NotificationEvent, NotificationEventType, NotificationService

        NotificationService(db).notify(
            NotificationEvent(
                event_type=NotificationEventType.SIGNUP_WELCOME,
                user_id=user.id,
                lang_code=lang_code,
            )
        )
    except Exception:
        pass
    
    # At registration, MFA is never enabled or required
    return AuthResponse(user=serialize_user(user, db), access_token=token, mfa_required=True, mfa_enabled=False)


def authenticate_user(db: Session, *, email: str, password: str, lang_code: str = "en") -> AuthResponse:
    user = _get_user_by_email(db, email)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_credentials", lang_code))

    try:
        password_is_valid = verify_password(password, user.password_hash)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_credentials", lang_code)) from exc

    if not password_is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_credentials", lang_code))

    mfa_record = _get_mfa_record(db, user.id)
    mfa_enabled = bool(mfa_record and mfa_record.is_verified)
    
    settings = get_settings()
    auth_ttl = get_runtime_int(db, "auth_token_ttl_minutes", settings.auth_token_ttl_minutes)
    mfa_ttl = get_runtime_int(db, "mfa_secret_token_ttl_minutes", settings.mfa_secret_token_ttl_minutes)

    # For customer users, show both true if MFA is enabled
    if str(user.role) == UserRole.customer.value:
        if bool(user.mfa_required) and mfa_enabled:
            challenge_token = create_mfa_challenge_token(user_id=str(user.id), role=str(user.role), ttl_minutes=mfa_ttl)
            return AuthResponse(
                user=serialize_user(user, db),
                access_token=None,
                challenge_token=challenge_token,
                mfa_required=True,
                mfa_enabled=True,
            )
        token = create_access_token(user_id=str(user.id), role=str(user.role), ttl_minutes=auth_ttl)
        _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
        db.commit()
        return AuthResponse(
            user=serialize_user(user, db),
            access_token=token,
            mfa_required=bool(user.mfa_required),
            mfa_enabled=mfa_enabled,
        )
    # For other users, keep existing logic
    if mfa_enabled:
        challenge_token = create_mfa_challenge_token(user_id=str(user.id), role=str(user.role), ttl_minutes=mfa_ttl)
        return AuthResponse(
            user=serialize_user(user, db),
            access_token=None,
            challenge_token=challenge_token,
            mfa_required=True,
            mfa_enabled=True,
        )
    token = create_access_token(user_id=str(user.id), role=str(user.role), ttl_minutes=auth_ttl)
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()
    return AuthResponse(user=serialize_user(user, db), access_token=token, mfa_required=False, mfa_enabled=False)


def verify_mfa_challenge(db: Session, *, challenge_token: str, code: str, lang_code: str = "en") -> AuthResponse:
    claims = verify_signed_token(challenge_token, token_type="mfa_challenge")
    try:
        user_id = UUID(str(claims.get("sub", "")))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_token_subject", lang_code)) from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_credentials", lang_code))

    mfa_record = _get_mfa_record(db, user.id)
    if mfa_record is None or not mfa_record.is_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("mfa_not_enabled", lang_code))

    code = code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_mfa_code", lang_code))

    secret = decrypt_secret(mfa_record.secret_encrypted)
    if not verify_totp_code(secret, code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=translate("invalid_mfa_code", lang_code))

    settings = get_settings()
    auth_ttl = get_runtime_int(db, "auth_token_ttl_minutes", settings.auth_token_ttl_minutes)
    token = create_access_token(user_id=str(user.id), role=str(user.role), ttl_minutes=auth_ttl)
    _audit(db, actor_user=user, action=AuditAction.auth_login, target_entity="user", target_id=user.id)
    db.commit()

    return AuthResponse(user=serialize_user(user, db), access_token=token, mfa_required=False, mfa_enabled=True)


def start_mfa_enrollment(db: Session, *, user: User, lang_code: str = "en") -> MfaSetupDetailsResponse:
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


def confirm_mfa_enrollment(db: Session, *, user: User, code: str, lang_code: str = "en") -> AuthResponse:
    record = _get_mfa_record(db, user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("mfa_not_initialized", lang_code))

    code = code.strip()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("invalid_mfa_code", lang_code))

    secret = decrypt_secret(record.secret_encrypted)
    if not verify_totp_code(secret, code):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("invalid_mfa_code", lang_code))

    record.is_verified = True
    db.commit()

    settings = get_settings()
    auth_ttl = get_runtime_int(db, "auth_token_ttl_minutes", settings.auth_token_ttl_minutes)
    token = create_access_token(user_id=str(user.id), role=str(user.role), ttl_minutes=auth_ttl)
    _audit(db, actor_user=user, action=AuditAction.auth_mfa_verify, target_entity="user", target_id=user.id)
    db.commit()

    return AuthResponse(user=serialize_user(user, db), access_token=token, mfa_required=False, mfa_enabled=True)


def update_user_role(db: Session, *, actor_user: User, user_id: UUID, role_code: UserRoleCode, lang_code: str = "en") -> AuthResponse:
    if actor_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("insufficient_permissions", lang_code))

    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))

    user.role = _code_to_role(role_code)
    _audit(db, actor_user=actor_user, action=AuditAction.user_role_change, target_entity="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return AuthResponse(user=serialize_user(user, db), mfa_required=False, mfa_enabled=bool(_get_mfa_record(db, user.id)))


def issue_forgot_password_reset(
    db: Session,
    *,
    email: str,
    lang_code: str = "en",
    production_base_url: str | None = None,
) -> None:
    user = _get_user_by_email(db, email)
    if user is None or not user.is_active:
        return

    # Invalidate existing unused tokens for this user.
    existing = db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for token_row in existing:
        token_row.used_at = now

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(raw_token)
    expires_at = now + timedelta(minutes=30)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            issued_by_user_id=None,
            token_hash=token_hash,
            reason="Forgot password self-service",
            expires_at=expires_at,
        )
    )
    db.add(
        AuditLog(
            actor_user_id=None,
            actor_role=None,
            action=AuditAction.auth_password_change,
            target_entity="user",
            target_id=user.id,
            target_user_id=user.id,
            changes_summary="Issued forgot-password token",
            before_json=None,
            after_json={"password_reset_issued": True},
        )
    )
    db.commit()

    from app.services.notifications import NotificationEvent, NotificationEventType, NotificationService
    notification = NotificationService(db)
    notification.notify(
        NotificationEvent(
            event_type=NotificationEventType.PASSWORD_RESET_ISSUED,
            user_id=user.id,
            lang_code=lang_code,
            context={
                "reset_token": raw_token,
                "production_base_url": production_base_url,
            },
        )
    )


def reset_password_with_token(
    db: Session,
    *,
    token: str,
    new_password: str,
    confirm_password: str,
    lang_code: str = "en",
) -> None:
    if new_password != confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password_mismatch")

    validation_error = get_password_validation_error(new_password)
    if validation_error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=validation_error)

    token_hash = _hash_reset_token(token)
    now = datetime.now(timezone.utc)
    reset_row = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    if reset_row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_token")

    user = db.get(User, reset_row.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_not_found")

    user.password_hash = hash_password(new_password)
    reset_row.used_at = now
    db.add(
        AuditLog(
            actor_user_id=user.id,
            actor_role=str(user.role),
            action=AuditAction.auth_password_change,
            target_entity="user",
            target_id=user.id,
            target_user_id=user.id,
            changes_summary="Password reset via token",
        )
    )
    db.commit()


def issue_email_verification_request(
    db: Session,
    *,
    user: User,
    lang_code: str = "en",
    production_base_url: str | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)

    user.email_verification_token_hash = token_hash
    user.email_verification_sent_at = now
    user.email_verification_expires_at = now + timedelta(hours=24)
    db.add(user)
    db.commit()

    try:
        from app.services.notifications import NotificationEvent, NotificationEventType, NotificationService

        NotificationService(db).notify(
            NotificationEvent(
                event_type=NotificationEventType.EMAIL_VERIFICATION_REQUESTED,
                user_id=user.id,
                lang_code=lang_code,
                context={
                    "verification_token": raw_token,
                    "production_base_url": production_base_url,
                },
            )
        )
    except Exception:
        pass


def confirm_email_verification(
    db: Session,
    *,
    token: str,
    lang_code: str = "en",
) -> AuthResponse:
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    user = db.scalar(
        select(User).where(
            User.email_verification_token_hash == token_hash,
            User.email_verification_expires_at.is_not(None),
            User.email_verification_expires_at > now,
        )
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("invalid_token", lang_code))

    user.email_verified = True
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None
    db.add(user)

    _audit(db, actor_user=user, action=AuditAction.auth_profile_update, target_entity="user", target_id=user.id)
    db.commit()
    db.refresh(user)

    return AuthResponse(user=serialize_user(user, db), mfa_required=False, mfa_enabled=bool(_get_mfa_record(db, user.id)))