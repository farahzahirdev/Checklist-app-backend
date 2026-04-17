from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.checklist import Checklist, ChecklistStatus, ChecklistType, ChecklistTranslation
from app.schemas.checklist import CustomerChecklistResponse, ChecklistTypeInfo
from typing import List

router = APIRouter(prefix="/checklists", tags=["checklists"])

@router.get("/", response_model=List[CustomerChecklistResponse], summary="List published checklists for customers")
def list_customer_checklists(db: Session = Depends(get_db)):
    # Query all published checklists
    checklists = db.query(Checklist).filter(Checklist.status_code_id == 2).all()  # 2 = published
    result = []
    for checklist in checklists:
        # Get type
        checklist_type = db.query(ChecklistType).filter(ChecklistType.id == checklist.checklist_type_id).first()
        # Get translation for title (if any)
        translation = db.query(ChecklistTranslation).filter(ChecklistTranslation.checklist_id == checklist.id).first()
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
    return result
