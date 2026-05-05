from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import UserCompanyAssignment
from app.models.user import User, UserRole


def resolve_company_id(user: User, company_id: UUID | None = None) -> UUID | None:
    if company_id is not None:
        return company_id

    primary_company_id = getattr(user, "primary_company_id", None)
    if primary_company_id in (None, ""):
        return None

    try:
        return UUID(str(primary_company_id))
    except (TypeError, ValueError):
        return None


def user_has_company_access(db: Session, *, user: User, company_id: UUID | None) -> bool:
    if company_id is None or user.role == UserRole.admin:
        return True

    assignment_exists = db.scalar(
        select(UserCompanyAssignment.id).where(
            UserCompanyAssignment.user_id == user.id,
            UserCompanyAssignment.company_id == company_id,
            UserCompanyAssignment.is_active.is_(True),
        )
    )
    return assignment_exists is not None
