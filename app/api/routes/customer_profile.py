"""
Customer Profile Management API

Endpoints for authenticated customers to:
- View their profile data
- Update profile information
- Change password
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    CustomerMfaSupportRequest,
    CustomerProfileResponse,
    EmailPreferencesResponse,
    EmailPreferencesUpdateRequest,
    ProfileCompletionItem,
    ProfileCompletionResponse,
    UpdateProfileRequest,
)
from app.schemas.support_ticket import SupportTicketResponse
from app.services.support_tickets import create_ticket
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate

router = APIRouter(prefix="/customer", tags=["customer-profile"])


def _serialize_profile(user: User, db: Session) -> dict:
    """Serialize user profile with company context."""
    from app.models.company import Company
    
    profile_data = {
        "id": user.id,
        "email": user.email,
        "email_verified": bool(user.email_verified),
        "email_verification_sent_at": user.email_verification_sent_at.isoformat() if user.email_verification_sent_at else None,
        "full_name": user.full_name,
        "username": user.username,
        "job_title": user.job_title,
        "department": user.department,
        "preferred_language": user.preferred_language or "en",
        "notifications_enabled": bool(user.email_notifications_enabled),
        "reports_alert": bool(user.email_pref_reports_alert),
        "payment_success_alert": bool(user.email_pref_payment_success_alert),
        "assessment_submitted_alert": bool(user.email_pref_assessment_submitted),
        "assessment_started_alert": bool(user.email_pref_assessment_started),
        "primary_company_id": user.primary_company_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if hasattr(user, 'created_at') and user.created_at else None,
        "updated_at": user.updated_at.isoformat() if hasattr(user, 'updated_at') and user.updated_at else None,
        "company_name": None,
        "company_industry": None,
        "company_size": None,
        "company_region": None,
        "company_email": None,
        "company_website": None,
        "company_slug": None,
        "company_country": None,
        "company_description": None,
        "billing_contact_name": None,
        "billing_email": None,
        "billing_phone": None,
        "billing_address_line1": None,
        "billing_address_line2": None,
        "billing_city": None,
        "billing_state": None,
        "billing_postal_code": None,
        "billing_country": None,
        "billing_tax_id": None,
    }
    
    # If user has a primary company, fetch its details
    if user.primary_company_id:
        company = db.query(Company).filter(Company.id == user.primary_company_id).first()
        if company:
            profile_data["company_name"] = company.name
            profile_data["company_industry"] = company.industry
            profile_data["company_size"] = company.size
            profile_data["company_region"] = company.region
            profile_data["company_email"] = company.email
            profile_data["company_website"] = company.website
            profile_data["company_slug"] = company.slug
            profile_data["company_country"] = company.country
            profile_data["company_description"] = company.description
            profile_data["billing_contact_name"] = company.billing_contact_name
            profile_data["billing_email"] = company.billing_email
            profile_data["billing_phone"] = company.billing_phone
            profile_data["billing_address_line1"] = company.billing_address_line1
            profile_data["billing_address_line2"] = company.billing_address_line2
            profile_data["billing_city"] = company.billing_city
            profile_data["billing_state"] = company.billing_state
            profile_data["billing_postal_code"] = company.billing_postal_code
            profile_data["billing_country"] = company.billing_country
            profile_data["billing_tax_id"] = company.billing_tax_id
    
    return profile_data


def _build_profile_completion(user: User, db: Session) -> ProfileCompletionResponse:
    from app.models.company import Company

    company = None
    if user.primary_company_id:
        company = db.query(Company).filter(Company.id == user.primary_company_id).first()

    personal_complete = all(
        bool((value or "").strip())
        for value in [user.full_name, user.username, user.job_title, user.department]
    )

    company_complete = bool(
        company
        and (company.name or "").strip()
        and (company.slug or "").strip()
        and (company.industry or "").strip()
        and (company.size or "").strip()
        and (company.region or "").strip()
        and (company.country or "").strip()
        and (company.website or "").strip()
    )

    mfa_record = getattr(user, "mfa_totp", None)
    mfa_complete = bool(mfa_record and mfa_record.is_verified)
    email_verified_complete = bool(user.email_verified)

    notification_complete = all(
        value is not None
        for value in [
            user.email_notifications_enabled,
            user.email_pref_reports_alert,
            user.email_pref_payment_success_alert,
            user.email_pref_assessment_submitted,
            user.email_pref_assessment_started,
        ]
    )

    billing_complete = bool(
        company
        and (company.billing_contact_name or "").strip()
        and (company.billing_email or "").strip()
        and (company.billing_address_line1 or "").strip()
        and (company.billing_city or "").strip()
        and (company.billing_postal_code or "").strip()
        and (company.billing_country or "").strip()
    )

    checks: list[ProfileCompletionItem] = [
        ProfileCompletionItem(section="profile", field="personal_details", label="Personal details completion", completed=personal_complete),
        ProfileCompletionItem(section="company", field="organizational_company_details", label="Organizational/company details completion", completed=company_complete),
        ProfileCompletionItem(section="security", field="email_verified", label="Email verification completion", completed=email_verified_complete),
        ProfileCompletionItem(section="security", field="mfa_setup", label="MFA setup completion", completed=mfa_complete),
        ProfileCompletionItem(section="preferences", field="notification_preferences", label="Notification preference configuration completion", completed=notification_complete),
        ProfileCompletionItem(section="billing", field="billing_details", label="Billing details completion", completed=billing_complete),
    ]

    completed_fields = [item for item in checks if item.completed]
    missing_fields = [item for item in checks if not item.completed]
    total = len(checks)
    completion_percent = round((len(completed_fields) / total) * 100.0, 2) if total else 100.0

    return ProfileCompletionResponse(
        completion_percent=completion_percent,
        is_complete=len(missing_fields) == 0,
        missing_fields=missing_fields,
        completed_fields=completed_fields,
    )


def _serialize_email_preferences(user: User) -> EmailPreferencesResponse:
    return EmailPreferencesResponse(
        notifications_enabled=bool(user.email_notifications_enabled),
        reports_alert=bool(user.email_pref_reports_alert),
        payment_success_alert=bool(user.email_pref_payment_success_alert),
        assessment_submitted_alert=bool(user.email_pref_assessment_submitted),
        assessment_started_alert=bool(user.email_pref_assessment_started),
    )


@router.get(
    "/profile",
    response_model=CustomerProfileResponse,
    summary="Get Customer Profile",
    description="Retrieve authenticated customer's profile data including company context.",
)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> CustomerProfileResponse:
    """
    Get the current user's profile information.
    
    Returns:
        CustomerProfileResponse with user and company context
    """
    lang_code = get_language_code(http_request, db) if http_request else "en"
    
    try:
        profile_data = _serialize_profile(current_user, db)
        return CustomerProfileResponse(**profile_data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("profile_retrieval_failed", lang_code)
        ) from exc


@router.get(
    "/profile/completion",
    response_model=ProfileCompletionResponse,
    summary="Get Profile Completion",
    description="Returns what profile/company setup fields are still missing for the authenticated user.",
)
def get_profile_completion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileCompletionResponse:
    return _build_profile_completion(current_user, db)


@router.get(
    "/profile/email-preferences",
    response_model=EmailPreferencesResponse,
    summary="Get Email Preferences",
    description="Returns user notification preferences for report/payment/assessment emails.",
)
def get_email_preferences(
    current_user: User = Depends(get_current_user),
) -> EmailPreferencesResponse:
    return _serialize_email_preferences(current_user)


@router.patch(
    "/profile/email-preferences",
    response_model=EmailPreferencesResponse,
    summary="Update Email Preferences",
    description="Update user email notifications. notifications_enabled works as master on/off toggle.",
)
def update_email_preferences(
    request: EmailPreferencesUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailPreferencesResponse:
    if request.notifications_enabled is not None:
        current_user.email_notifications_enabled = request.notifications_enabled

    if request.reports_alert is not None:
        current_user.email_pref_reports_alert = request.reports_alert

    if request.payment_success_alert is not None:
        current_user.email_pref_payment_success_alert = request.payment_success_alert

    if request.assessment_submitted_alert is not None:
        current_user.email_pref_assessment_submitted = request.assessment_submitted_alert

    if request.assessment_started_alert is not None:
        current_user.email_pref_assessment_started = request.assessment_started_alert

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _serialize_email_preferences(current_user)


@router.patch(
    "/profile",
    response_model=CustomerProfileResponse,
    summary="Update Customer Profile",
    description="Update customer's profile information and optionally auto-create/update company details.",
)
def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> CustomerProfileResponse:
    """
    Update the current user's profile and optionally company information.
    If company details are provided, auto-creates or updates company record.
    
    Args:
        request: Update data (all fields optional)
        current_user: Authenticated user
        db: Database session
        http_request: HTTP request for language detection
    
    Returns:
        Updated CustomerProfileResponse with company context
    """
    from app.models.company import Company
    
    lang_code = get_language_code(http_request, db) if http_request else "en"
    
    try:
        # Update user profile fields if provided
        if request.full_name is not None:
            current_user.full_name = request.full_name.strip()
        
        if request.username is not None:
            new_username = request.username.strip().lower()
            
            # Check if username is already taken (by another user)
            if new_username != (current_user.username or "").lower():
                existing = db.query(User).filter(
                    User.username == new_username,
                    User.id != current_user.id
                ).first()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=translate("username_already_taken", lang_code)
                    )
            
            current_user.username = new_username
        
        if request.job_title is not None:
            current_user.job_title = request.job_title.strip()
        
        if request.department is not None:
            current_user.department = request.department.strip()

        if request.preferred_language is not None:
            normalized_lang = request.preferred_language.strip().lower()
            if normalized_lang == "cz":
                normalized_lang = "cs"
            current_user.preferred_language = normalized_lang

        if request.notifications_enabled is not None:
            current_user.email_notifications_enabled = request.notifications_enabled

        if request.reports_alert is not None:
            current_user.email_pref_reports_alert = request.reports_alert

        if request.payment_success_alert is not None:
            current_user.email_pref_payment_success_alert = request.payment_success_alert

        if request.assessment_submitted_alert is not None:
            current_user.email_pref_assessment_submitted = request.assessment_submitted_alert

        if request.assessment_started_alert is not None:
            current_user.email_pref_assessment_started = request.assessment_started_alert
        
        # Handle company creation/update if any company fields provided
        company_fields_provided = any([
            request.company_name is not None,
            request.company_slug is not None,
            request.company_email is not None,
            request.company_website is not None,
            request.company_industry is not None,
            request.company_country is not None,
            request.company_size is not None,
            request.company_description is not None,
            request.billing_contact_name is not None,
            request.billing_email is not None,
            request.billing_phone is not None,
            request.billing_address_line1 is not None,
            request.billing_address_line2 is not None,
            request.billing_city is not None,
            request.billing_state is not None,
            request.billing_postal_code is not None,
            request.billing_country is not None,
            request.billing_tax_id is not None,
        ])
        
        if company_fields_provided:
            # If user doesn't have a company, create one
            if not current_user.primary_company_id:
                # Generate slug if not provided
                company_slug = request.company_slug
                if not company_slug and request.company_name:
                    company_slug = request.company_name.strip().lower().replace(" ", "-")
                
                if not company_slug:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Company name or slug is required to create a company"
                    )
                
                # Check slug uniqueness
                existing_slug = db.query(Company).filter(Company.slug == company_slug.lower()).first()
                if existing_slug:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=translate("company_slug_exists", lang_code)
                    )
                
                # Create new company
                from app.models.company import UserCompanyAssignment
                company = Company(
                    name=request.company_name.strip() if request.company_name else "My Company",
                    slug=company_slug.lower(),
                    email=request.company_email.strip() if request.company_email else None,
                    website=request.company_website.strip() if request.company_website else None,
                    industry=request.company_industry.strip() if request.company_industry else None,
                    country=request.company_country.strip() if request.company_country else None,
                    size=request.company_size.strip() if request.company_size else None,
                    description=request.company_description.strip() if request.company_description else None,
                    billing_contact_name=request.billing_contact_name.strip() if request.billing_contact_name else None,
                    billing_email=request.billing_email.strip() if request.billing_email else None,
                    billing_phone=request.billing_phone.strip() if request.billing_phone else None,
                    billing_address_line1=request.billing_address_line1.strip() if request.billing_address_line1 else None,
                    billing_address_line2=request.billing_address_line2.strip() if request.billing_address_line2 else None,
                    billing_city=request.billing_city.strip() if request.billing_city else None,
                    billing_state=request.billing_state.strip() if request.billing_state else None,
                    billing_postal_code=request.billing_postal_code.strip() if request.billing_postal_code else None,
                    billing_country=request.billing_country.strip() if request.billing_country else None,
                    billing_tax_id=request.billing_tax_id.strip() if request.billing_tax_id else None,
                    is_active=True,
                )
                db.add(company)
                db.flush()
                
                # Create assignment
                assignment = UserCompanyAssignment(
                    user_id=current_user.id,
                    company_id=company.id,
                    role="owner",
                    is_active=True,
                )
                db.add(assignment)
                current_user.primary_company_id = company.id
            else:
                # Update existing company
                company = db.query(Company).filter(Company.id == current_user.primary_company_id).first()
                if company:
                    if request.company_name is not None:
                        company.name = request.company_name.strip()
                    if request.company_slug is not None:
                        new_slug = request.company_slug.strip().lower()
                        if new_slug != company.slug:
                            # Check uniqueness
                            existing_slug = db.query(Company).filter(
                                Company.slug == new_slug,
                                Company.id != company.id
                            ).first()
                            if existing_slug:
                                raise HTTPException(
                                    status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=translate("company_slug_exists", lang_code)
                                )
                        company.slug = new_slug
                    if request.company_email is not None:
                        company.email = request.company_email.strip() if request.company_email else None
                    if request.company_website is not None:
                        company.website = request.company_website.strip() if request.company_website else None
                    if request.company_industry is not None:
                        company.industry = request.company_industry.strip() if request.company_industry else None
                    if request.company_country is not None:
                        company.country = request.company_country.strip() if request.company_country else None
                    if request.company_size is not None:
                        company.size = request.company_size.strip() if request.company_size else None
                    if request.company_description is not None:
                        company.description = request.company_description.strip() if request.company_description else None
                    if request.billing_contact_name is not None:
                        company.billing_contact_name = request.billing_contact_name.strip() if request.billing_contact_name else None
                    if request.billing_email is not None:
                        company.billing_email = request.billing_email.strip() if request.billing_email else None
                    if request.billing_phone is not None:
                        company.billing_phone = request.billing_phone.strip() if request.billing_phone else None
                    if request.billing_address_line1 is not None:
                        company.billing_address_line1 = request.billing_address_line1.strip() if request.billing_address_line1 else None
                    if request.billing_address_line2 is not None:
                        company.billing_address_line2 = request.billing_address_line2.strip() if request.billing_address_line2 else None
                    if request.billing_city is not None:
                        company.billing_city = request.billing_city.strip() if request.billing_city else None
                    if request.billing_state is not None:
                        company.billing_state = request.billing_state.strip() if request.billing_state else None
                    if request.billing_postal_code is not None:
                        company.billing_postal_code = request.billing_postal_code.strip() if request.billing_postal_code else None
                    if request.billing_country is not None:
                        company.billing_country = request.billing_country.strip() if request.billing_country else None
                    if request.billing_tax_id is not None:
                        company.billing_tax_id = request.billing_tax_id.strip() if request.billing_tax_id else None
        
        db.commit()
        db.refresh(current_user)
        
        profile_data = _serialize_profile(current_user, db)
        return CustomerProfileResponse(**profile_data)
    
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("profile_update_failed", lang_code)
        ) from exc


@router.patch(
    "/profile/password",
    response_model=dict,
    summary="Change Password",
    description="Change the customer's account password with verification of current password.",
)
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> dict:
    """
    Change the current user's password.
    
    Args:
        request: Current and new password
        current_user: Authenticated user
        db: Database session
        http_request: HTTP request for language detection
    
    Returns:
        Success message
    """
    lang_code = get_language_code(http_request, db) if http_request else "en"
    
    try:
        # Verify current password
        try:
            password_is_valid = verify_password(request.current_password, current_user.password_hash)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=translate("invalid_current_password", lang_code)
            ) from exc
        
        if not password_is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=translate("invalid_current_password", lang_code)
            )
        
        # Validate new password
        if request.new_password != request.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=translate("password_mismatch", lang_code)
            )
        
        # Check password strength
        from app.services.auth import get_password_validation_error
        validation_error = get_password_validation_error(request.new_password)
        if validation_error is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=translate(validation_error, lang_code)
            )
        
        # Prevent reusing same password
        if verify_password(request.new_password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=translate("new_password_same_as_current", lang_code)
            )
        
        # Update password
        current_user.password_hash = hash_password(request.new_password)
        db.commit()
        
        # Log password change in audit
        from app.models.audit_log import AuditLog, AuditAction
        audit_log = AuditLog(
            actor_user_id=current_user.id,
            actor_role=str(current_user.role),
            action=AuditAction.auth_password_change,
            target_entity="user",
            target_id=current_user.id,
        )
        db.add(audit_log)
        db.commit()
        
        return {
            "status": "success",
            "message": translate("password_changed_successfully", lang_code),
            "lang": lang_code
        }
    
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=translate("password_change_failed", lang_code)
        ) from exc


@router.post(
    "/profile/mfa-support-request",
    response_model=SupportTicketResponse,
    summary="Create MFA Support Request",
    description="Creates a support ticket for MFA reset/disable request and notifies admin/auditor recipients by email.",
)
def create_mfa_support_request(
    request: CustomerMfaSupportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    http_request: Request = None,
) -> SupportTicketResponse:
    from app.models.company import Company
    from app.models.user import UserRole
    from app.services.notifications import NotificationEvent, NotificationEventType, NotificationService

    lang_code = get_language_code(http_request, db) if http_request else "en"

    if str(current_user.role) != UserRole.customer.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("insufficient_permissions", lang_code))

    company = None
    if current_user.primary_company_id:
        company = db.query(Company).filter(Company.id == current_user.primary_company_id).first()

    request_type_label = {
        "cs": {"reset": "Reset MFA", "disable": "Vypnutí MFA"},
        "en": {"reset": "MFA reset", "disable": "MFA disable"},
    }
    localized_label = request_type_label.get(lang_code, request_type_label["en"]).get(request.request_type, request.request_type)
    subject = f"MFA request: {localized_label}"

    details_lines = [
        f"MFA request type: {request.request_type}",
        f"User ID: {current_user.id}",
        f"Email: {current_user.email}",
        f"Full name: {current_user.full_name or '-'}",
        f"Username: {current_user.username or '-'}",
        f"Company: {company.name if company else '-'}",
        f"Company slug: {company.slug if company else '-'}",
        "",
        "User message:",
        request.message.strip(),
    ]
    body = "\n".join(details_lines)

    ticket = create_ticket(db, customer=current_user, subject=subject, message=body)

    try:
        NotificationService(db).notify(
            NotificationEvent(
                event_type=NotificationEventType.MFA_SUPPORT_REQUEST,
                user_id=current_user.id,
                actor_id=current_user.id,
                lang_code=lang_code,
                context={
                    "support_ticket_id": str(ticket["id"]),
                    "mfa_request_type": request.request_type,
                    "mfa_request_type_label": localized_label,
                    "mfa_request_message": request.message.strip(),
                    "customer_id": str(current_user.id),
                    "customer_email": current_user.email,
                    "customer_name": current_user.full_name or "",
                    "customer_username": current_user.username or "",
                    "customer_company_name": company.name if company else "",
                    "customer_company_slug": company.slug if company else "",
                },
            )
        )
    except Exception:
        # Ticket creation is primary action; avoid failing request when notification dispatch fails.
        pass

    return SupportTicketResponse(**ticket)
