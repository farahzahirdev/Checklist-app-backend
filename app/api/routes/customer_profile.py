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
    CustomerProfileResponse,
    UpdateProfileRequest,
)
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate

router = APIRouter(prefix="/customer", tags=["customer-profile"])


def _serialize_profile(user: User, db: Session) -> dict:
    """Serialize user profile with company context."""
    from app.models.company import Company
    
    profile_data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "username": user.username,
        "job_title": user.job_title,
        "department": user.department,
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
    
    return profile_data


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
