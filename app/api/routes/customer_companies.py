"""Customer-facing Company (tenant) management endpoints.

Allows customers to create companies, manage their company profile, and invite/assign users
for their own companies. Uses the existing `Company` and `UserCompanyAssignment` models.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.company import Company, UserCompanyAssignment
from app.models.user import User
from app.schemas.company import (
    CreateCompanyRequest,
    CompanyResponse,
    CompanyListResponse,
    CompanyDetailResponse,
    UserCompanyListResponse,
)
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate


router = APIRouter(prefix="/customer/companies", tags=["customer-companies"])


def _user_assignment(db: Session, user_id: UUID, company_id: UUID):
    return db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.user_id == user_id,
        UserCompanyAssignment.company_id == company_id,
        UserCompanyAssignment.is_active == True,
    ).first()


@router.get("/", response_model=CompanyListResponse)
def list_my_companies(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """List companies the current user is assigned to."""
    lang = get_language_code(request, db)

    query = db.query(UserCompanyAssignment).filter(UserCompanyAssignment.user_id == current_user.id)
    total = query.count()
    assignments = query.order_by(desc(UserCompanyAssignment.assigned_at)).offset(skip).limit(limit).all()

    companies = [a.company for a in assignments if a.company is not None]
    return {"total": len(companies), "companies": companies, "skip": skip, "limit": limit}


@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    request: Request,
    payload: CreateCompanyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Company:
    """Create a new company and assign current user as owner."""
    lang = get_language_code(request, db)

    existing = db.query(Company).filter(Company.slug == payload.slug.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail=translate("company_slug_exists", lang))

    company = Company(
        name=payload.name.strip(),
        slug=payload.slug.lower(),
        email=payload.email,
        website=payload.website,
        region=payload.region,
        country=payload.country,
        industry=payload.industry,
        size=payload.size,
        description=payload.description,
        compliance_framework=payload.compliance_framework,
        is_active=True,
    )
    db.add(company)
    db.flush()

    assignment = UserCompanyAssignment(
        user_id=current_user.id,
        company_id=company.id,
        role="owner",
        is_active=True,
    )
    db.add(assignment)

    # Optionally set user's primary_company_id for convenience
    current_user.primary_company_id = company.id
    db.add(current_user)

    db.commit()
    db.refresh(company)

    return company


@router.get("/{company_id}", response_model=CompanyDetailResponse)
def get_company_detail(
    company_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get company details if user is assigned to it."""
    lang = get_language_code(request, db)

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail=translate("company_not_found", lang))

    assignment = _user_assignment(db, current_user.id, company_id)
    if not assignment and current_user.role != "admin":
        raise HTTPException(status_code=403, detail=translate("insufficient_permissions", lang))

    user_count = db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.company_id == company_id, UserCompanyAssignment.is_active == True
    ).count()

    return {**company.__dict__, "user_count": user_count}


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company_customer(
    company_id: UUID,
    request: Request,
    payload: CreateCompanyRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Company:
    """Update company details if user is owner or manager."""
    lang = get_language_code(request, db)

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail=translate("company_not_found", lang))

    assignment = _user_assignment(db, current_user.id, company_id)
    if not assignment or assignment.role not in ("owner", "manager"):
        raise HTTPException(status_code=403, detail=translate("insufficient_permissions", lang))

    # Update permitted fields
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

    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}/users", response_model=UserCompanyListResponse)
def list_company_users_customer(
    company_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """List users in a company if requesting user is assigned."""
    lang = get_language_code(request, db)

    assignment = _user_assignment(db, current_user.id, company_id)
    if not assignment and current_user.role != "admin":
        raise HTTPException(status_code=403, detail=translate("insufficient_permissions", lang))

    query = db.query(UserCompanyAssignment).filter(UserCompanyAssignment.company_id == company_id)
    total = query.count()
    assignments = query.order_by(desc(UserCompanyAssignment.assigned_at)).offset(skip).limit(limit).all()

    detailed = []
    for a in assignments:
        detailed.append({**a.__dict__, "user_email": a.user.email, "company_name": a.company.name, "company_slug": a.company.slug})

    return {"total": total, "assignments": detailed, "skip": skip, "limit": limit}



@router.patch("/{company_id}/select", response_model=CompanyResponse)
def select_primary_company(
    company_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Company:
    """Set the user's primary company (for default tenant-scoped actions)."""
    lang = get_language_code(request, db)

    assignment = _user_assignment(db, current_user.id, company_id)
    if not assignment:
        raise HTTPException(status_code=403, detail=translate("insufficient_permissions", lang))

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail=translate("company_not_found", lang))

    current_user.primary_company_id = company.id
    db.add(current_user)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_company(
    company_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """Allow current user to leave a company (deactivate their assignment). Owners cannot leave without transferring ownership."""
    lang = get_language_code(request, db)

    assignment = db.query(UserCompanyAssignment).filter(
        UserCompanyAssignment.user_id == current_user.id,
        UserCompanyAssignment.company_id == company_id,
        UserCompanyAssignment.is_active == True,
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail=translate("assignment_not_found", lang))

    if assignment.role == "owner":
        raise HTTPException(status_code=400, detail=translate("owner_cannot_leave", lang))

    assignment.is_active = False
    db.add(assignment)
    db.commit()
    return None
