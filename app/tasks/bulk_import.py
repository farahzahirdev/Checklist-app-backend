import base64

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.schemas.bulk_checklist import BulkChecklistCreateResponse, ColumnMapping
from app.services.bulk_checklist import create_checklist_from_file


@celery_app.task(name="app.tasks.bulk_import.create_checklist_task", bind=False)
def create_checklist_task(
    actor_id: int,
    file_content_b64: str,
    file_name: str,
    column_mapping_data: dict,
    checklist_title: str,
    checklist_description: str | None,
    checklist_type_code: str,
) -> dict:
    """Execute bulk checklist creation in a background worker."""
    file_content = base64.b64decode(file_content_b64)
    db: Session = SessionLocal()
    try:
        column_mapping = ColumnMapping.model_validate(column_mapping_data)
        response = create_checklist_from_file(
            db=db,
            actor=actor_id,
            file_content=file_content,
            file_name=file_name,
            column_mapping=column_mapping,
            checklist_title=checklist_title,
            checklist_description=checklist_description,
            checklist_type_code=checklist_type_code,
        )
        serialized = response.model_dump()
        if serialized.get("checklist_id") is not None:
            serialized["checklist_id"] = str(serialized["checklist_id"])
        return serialized
    finally:
        db.close()
