"""
Company Management Routes

Administrative endpoints for managing companies and user-company associations.
Supports multi-company audit scenarios where users have roles in different companies.
"""
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.api.dependencies.auth import require_admin_only
from app.models.company import Company, UserCompanyAssignment
from app.models.user import User
from app.schemas.company import (
    AssignUserToCompanyRequest,
    CompanyDetailResponse,
    CompanyListResponse,
    CompanyResponse,
    CreateCompanyRequest,
    UpdateCompanyRequest,
    UpdateUserCompanyRoleRequest,
    UserCompanyAssignmentResponse,
    UserCompanyDetailResponse,
    UserCompanyListResponse,
)
from app.services.rbac import RBACService
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/companies", tags=["admin", "companies"], dependencies=[Depends(require_admin_only())])


# ============================================================================
# COMPANY MANAGEMENT
# ============================================================================

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    request: Request,
    payload: CreateCompanyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Create a new company in the system.
    
    Only admins can create companies.
    """
    lang_code = get_language_code(request, db)
    
    # Check permission
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Check slug uniqueness
    existing = db.query(Company).filter(Company.slug == payload.slug.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Company slug '{payload.slug}' already exists"
        )
    
    # Create company
    company = Company(
        name=payload.name,
        slug=payload.slug.lower(),
        email=payload.email,
        website=payload.website,
        region=payload.region,
        country=payload.country,
        industry=payload.industry,
        size=payload.size,
        description=payload.description,
        compliance_framework=payload.compliance_framework,
        is_active=True
    )
    
    db.add(company)
    db.commit()
    db.refresh(company)
    
    logger.info(f"Company created: {company.name} (ID: {company.id}) by user {current_user.email}")
    
    return company


@router.get("/", response_model=CompanyListResponse)
def list_companies(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: str | None = Query(None, description="Search by name or slug"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    industry: str | None = Query(None, description="Filter by industry"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    List all companies.
    
    Supports filtering by name, slug, industry, and active status.
    """
    lang_code = get_language_code(request, db)
    
    # Check permission
    if not RBACService.has_permission(db, current_user.id, "user_management", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    query = db.query(Company)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(Company.name.ilike(search_term), Company.slug.ilike(search_term)))
    
    if is_active is not None:
        query = query.filter(Company.is_active == is_active)
    
    if industry:
        query = query.filter(Company.industry == industry)
    
    total = query.count()
    companies = query.order_by(desc(Company.created_at)).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "companies": companies,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{company_id}", response_model=CompanyDetailResponse)
def get_company(
    company_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Get details of a specific company with user count.
    """
    lang_code = get_language_code(request, db)
    
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("company_not_found", lang_code)
        )
    
    # Count active users
    user_count = db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.company_id == company_id,
        UserCompanyAssignment.is_active == True
    ).count()
    
    return {
        **company.__dict__,
        "user_count": user_count
    }


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: UUID,
    request: Request,
    payload: UpdateCompanyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Update company information.
    
    Only admins can update companies.
    """
    lang_code = get_language_code(request, db)
    
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("company_not_found", lang_code)
        )
    
    # Update fields if provided
    if payload.name is not None:
        company.name = payload.name
    if payload.email is not None:
        company.email = payload.email
    if payload.website is not None:
        company.website = payload.website
    if payload.region is not None:
        company.region = payload.region
    if payload.country is not None:
        company.country = payload.country
    if payload.industry is not None:
        company.industry = payload.industry
    if payload.size is not None:
        company.size = payload.size
    if payload.description is not None:
        company.description = payload.description
    if payload.compliance_framework is not None:
        company.compliance_framework = payload.compliance_framework
    if payload.is_active is not None:
        company.is_active = payload.is_active
    
    db.commit()
    db.refresh(company)
    
    logger.info(f"Company updated: {company.name} (ID: {company.id}) by user {current_user.email}")
    
    return company


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Delete a company and all associated user assignments.
    
    Only admins can delete companies.
    """
    lang_code = get_language_code(request, db)
    
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("company_not_found", lang_code)
        )
    
    logger.info(f"Company deleted: {company.name} (ID: {company.id}) by user {current_user.email}")
    
    db.delete(company)
    db.commit()


# ============================================================================
# USER-COMPANY ASSOCIATION MANAGEMENT
# ============================================================================

@router.post("/{company_id}/users", response_model=UserCompanyAssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_user_to_company(
    company_id: UUID,
    request: Request,
    payload: AssignUserToCompanyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Assign a user to a company with a specific role.
    
    One user can be assigned to multiple companies with different roles.
    """
    lang_code = get_language_code(request, db)
    
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("company_not_found", lang_code)
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("user_not_found", lang_code)
        )
    
    # Check if assignment already exists
    existing = db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.user_id == payload.user_id,
        UserCompanyAssignment.company_id == company_id
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already assigned to this company"
        )
    
    # Create assignment
    assignment = UserCompanyAssignment(
        user_id=payload.user_id,
        company_id=company_id,
        role=payload.role,
        job_title=payload.job_title,
        department=payload.department,
        is_active=True
    )
    
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    
    logger.info(f"User {user.email} assigned to company {company.name} as {payload.role}")
    
    return assignment


@router.get("/{company_id}/users", response_model=UserCompanyListResponse)
def list_company_users(
    company_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_inactive: bool = Query(False, description="Include inactive assignments"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    List all users assigned to a company.
    """
    lang_code = get_language_code(request, db)
    
    if not RBACService.has_permission(db, current_user.id, "user_management", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Verify company exists
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("company_not_found", lang_code)
        )
    
    query = db.query(UserCompanyAssignment).filter(UserCompanyAssignment.company_id == company_id)
    
    if not include_inactive:
        query = query.filter(UserCompanyAssignment.is_active == True)
    
    total = query.count()
    assignments = query.order_by(desc(UserCompanyAssignment.assigned_at)).offset(skip).limit(limit).all()
    
    # Build detailed responses with user and company info
    detailed_assignments = []
    for assignment in assignments:
        detailed_assignments.append({
            **assignment.__dict__,
            "user_email": assignment.user.email,
            "company_name": company.name,
            "company_slug": company.slug,
        })
    
    return {
        "total": total,
        "assignments": detailed_assignments,
        "skip": skip,
        "limit": limit,
    }


@router.get("/users/{user_id}/companies", response_model=UserCompanyListResponse)
def get_user_companies(
    user_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    include_inactive: bool = Query(False, description="Include inactive assignments"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Get all companies a user is assigned to.
    
    Shows all companies where the user has a role.
    """
    lang_code = get_language_code(request, db)
    
    # User can view their own companies, admins can view any user
    if user_id != current_user.id:
        if not RBACService.has_permission(db, current_user.id, "user_management", "read"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate("insufficient_permissions", lang_code)
            )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("user_not_found", lang_code)
        )
    
    query = db.query(UserCompanyAssignment).filter(UserCompanyAssignment.user_id == user_id)
    
    if not include_inactive:
        query = query.filter(UserCompanyAssignment.is_active == True)
    
    total = query.count()
    assignments = query.order_by(desc(UserCompanyAssignment.assigned_at)).offset(skip).limit(limit).all()
    
    # Build detailed responses
    detailed_assignments = []
    for assignment in assignments:
        detailed_assignments.append({
            **assignment.__dict__,
            "user_email": user.email,
            "company_name": assignment.company.name,
            "company_slug": assignment.company.slug,
        })
    
    return {
        "total": total,
        "assignments": detailed_assignments,
        "skip": skip,
        "limit": limit,
    }


@router.put("/{company_id}/users/{user_id}", response_model=UserCompanyAssignmentResponse)
def update_user_company_role(
    company_id: UUID,
    user_id: UUID,
    request: Request,
    payload: UpdateUserCompanyRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Update a user's role and details within a company.
    """
    lang_code = get_language_code(request, db)
    
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    assignment = db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.company_id == company_id,
        UserCompanyAssignment.user_id == user_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not assigned to this company"
        )
    
    # Update fields if provided
    if payload.role is not None:
        assignment.role = payload.role
    if payload.job_title is not None:
        assignment.job_title = payload.job_title
    if payload.department is not None:
        assignment.department = payload.department
    if payload.is_active is not None:
        assignment.is_active = payload.is_active
    
    db.commit()
    db.refresh(assignment)
    
    logger.info(f"User {assignment.user.email} updated in company {assignment.company.name}")
    
    return assignment


@router.delete("/{company_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user_from_company(
    company_id: UUID,
    user_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove a user from a company (delete the assignment).
    """
    lang_code = get_language_code(request, db)
    
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    assignment = db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.company_id == company_id,
        UserCompanyAssignment.user_id == user_id
    ).first()
    
    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not assigned to this company"
        )
    
    logger.info(f"User {assignment.user.email} removed from company {assignment.company.name}")
    
    db.delete(assignment)
    db.commit()
