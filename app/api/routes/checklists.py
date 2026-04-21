from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.checklist import Checklist, ChecklistStatus, ChecklistType, ChecklistTranslation
from app.schemas.checklist import CustomerChecklistListResponse, CustomerChecklistResponse, ChecklistTypeInfo
from typing import List
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate

router = APIRouter(prefix="/checklists", tags=["checklists"])

@router.get("/", response_model=CustomerChecklistListResponse, summary="List published checklists for customers")
def list_customer_checklists(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for titles"),
    db: Session = Depends(get_db),
):
    lang_code = get_language_code(request, db)
    query = db.query(Checklist).filter(Checklist.status_code_id == 2)

    if search:
        search_term = f"%{search}%"
        query = query.outerjoin(ChecklistTranslation, ChecklistTranslation.checklist_id == Checklist.id).filter(
            or_(
                ChecklistTranslation.title.ilike(search_term),
                ChecklistTranslation.description.ilike(search_term),
            )
        )

    sort_column = Checklist.created_at
    if sort_by == "updated_at":
        sort_column = Checklist.updated_at
    elif sort_by == "version":
        sort_column = Checklist.version
    elif sort_by == "status":
        sort_column = Checklist.status

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    checklists = query.offset(skip).limit(limit).all()

    result = []
    for checklist in checklists:
        checklist_type = db.query(ChecklistType).filter(ChecklistType.id == checklist.checklist_type_id).first()
        translation = db.query(ChecklistTranslation).filter(ChecklistTranslation.checklist_id == checklist.id, ChecklistTranslation.language == lang_code).first()
        title = translation.title if translation else f"Checklist v{checklist.version}"
        result.append(CustomerChecklistResponse(
            id=checklist.id,
            title=title,
            checklist_type=ChecklistTypeInfo(
                id=checklist_type.id,
                code=checklist_type.code,
                name=checklist_type.name,
                description=checklist_type.description,
            ),
            version=f"v{checklist.version}.0",
            status=checklist.status.value if checklist.status else "",
            created_at=checklist.created_at,
            updated_at=checklist.updated_at,
        ))

    return {"total": total, "checklists": result, "skip": skip, "limit": limit}
