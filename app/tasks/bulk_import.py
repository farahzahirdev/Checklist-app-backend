import base64

from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.db.session import SessionLocal
from app.schemas.bulk_checklist import ColumnMapping
from app.services.bulk_checklist import create_checklist_from_file, replace_checklist_from_file

REQUIRED_MAPPING_FIELDS = [
    "section_name_col",
    "question_id_col",
    "legal_requirement_col",
    "question_text_col",
    "severity_col",
]


def _validate_column_mapping(column_mapping_data: dict) -> ColumnMapping:
    if not column_mapping_data or not isinstance(column_mapping_data, dict):
        raise ValueError("Column mapping data is required and must be a dictionary")

    missing_fields = [field for field in REQUIRED_MAPPING_FIELDS if field not in column_mapping_data]
    if missing_fields:
        raise ValueError(f"Missing required column mapping fields: {', '.join(missing_fields)}")

    return ColumnMapping.model_validate(column_mapping_data)


def _serialize_bulk_response(response) -> dict:
    serialized = response.model_dump()
    if serialized.get("checklist_id") is not None:
        serialized["checklist_id"] = str(serialized["checklist_id"])
    return serialized


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
        column_mapping = _validate_column_mapping(column_mapping_data)
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
        return _serialize_bulk_response(response)
    finally:
        db.close()


@celery_app.task(name="app.tasks.bulk_import.replace_checklist_task", bind=False)
def replace_checklist_task(
    actor_id: int,
    checklist_id: str,
    file_content_b64: str,
    file_name: str,
    column_mapping_data: dict,
    checklist_title: str | None,
    checklist_description: str | None,
) -> dict:
    """Replace an existing draft checklist's structure from Excel/CSV in a background worker."""
    file_content = base64.b64decode(file_content_b64)
    db: Session = SessionLocal()
    try:
        column_mapping = _validate_column_mapping(column_mapping_data)
        response = replace_checklist_from_file(
            db=db,
            actor=actor_id,
            checklist_id=checklist_id,
            file_content=file_content,
            file_name=file_name,
            column_mapping=column_mapping,
            checklist_title=checklist_title,
            checklist_description=checklist_description,
        )
        return _serialize_bulk_response(response)
    finally:
        db.close()
