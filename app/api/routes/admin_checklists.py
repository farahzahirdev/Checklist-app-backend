from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.admin_checklist import (
    AdminChecklistCreateRequest,
    AdminChecklistResponse,
    AdminChecklistUpdateRequest,
    AdminQuestionCreateRequest,
    AdminQuestionUpdateRequest,
    AdminQuestionResponse,
    AdminSectionCreateRequest,
    AdminSectionReorderRequest,
    AdminSectionUpdateRequest,
    AdminSectionResponse,
    PublishChecklistRequest,
)
from app.services.admin_checklist import (
    create_checklist,
    create_question,
    create_section,
    delete_checklist,
    delete_question,
    delete_section,
    get_checklist,
    get_question,
    list_checklists,
    list_questions,
    list_sections,
    publish_checklist,
    reorder_sections,
    update_checklist,
    update_question,
    update_section,
)

router = APIRouter(prefix="/admin/checklists", tags=["admin-checklists"])


@router.get(
    "",
    response_model=list[AdminChecklistResponse],
    summary="List Checklists",
    description="Admin-only list of all checklists available for publishing and assessment delivery.",
)
def admin_list_checklists(
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminChecklistResponse]:
    return list_checklists(db)


@router.post(
    "",
    response_model=AdminChecklistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Checklist",
    description="Creates a new checklist draft including metadata, version, and access configuration.",
)
def admin_create_checklist(
    request: AdminChecklistCreateRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    return create_checklist(db, actor=admin, payload=request)


@router.get(
    "/{checklist_id}",
    response_model=AdminChecklistResponse,
    summary="Get Checklist",
    description="Returns a single checklist with its current status and editable properties.",
)
def admin_get_checklist(
    checklist_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    checklist = get_checklist(db, checklist_id=checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")
    return checklist


@router.patch(
    "/{checklist_id}",
    response_model=AdminChecklistResponse,
    summary="Update Checklist",
    description="Partially updates checklist metadata such as title, version, locale settings, and rules.",
)
def admin_update_checklist(
    checklist_id: UUID,
    request: AdminChecklistUpdateRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    checklist = update_checklist(db, actor=admin, checklist_id=checklist_id, payload=request)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")
    return checklist


@router.patch(
    "/{checklist_id}/publish",
    response_model=AdminChecklistResponse,
    summary="Publish Checklist",
    description="Transitions a checklist to published state so customers can use it for assessments.",
)
def admin_publish_checklist(
    checklist_id: UUID,
    request: PublishChecklistRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    checklist = publish_checklist(db, actor=admin, checklist_id=checklist_id, payload=request)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")
    return checklist


@router.delete(
    "/{checklist_id}",
    response_model=dict[str, str],
    summary="Delete Checklist",
    description="Removes a checklist that is no longer needed. Returns not_found when checklist does not exist.",
)
def admin_delete_checklist(
    checklist_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_checklist(db, checklist_id=checklist_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")
    return {"message": "checklist_deleted"}


@router.get(
    "/{checklist_id}/sections",
    response_model=list[AdminSectionResponse],
    summary="List Sections",
    description="Lists all sections under the specified checklist in display order.",
)
def admin_list_sections(
    checklist_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminSectionResponse]:
    return list_sections(db, checklist_id=checklist_id)


@router.post(
    "/{checklist_id}/sections",
    response_model=AdminSectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Section",
    description="Creates a new checklist section and assigns chapter metadata and ordering.",
)
def admin_create_section(
    checklist_id: UUID,
    request: AdminSectionCreateRequest,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSectionResponse:
    return create_section(db, checklist_id=checklist_id, payload=request)


@router.patch(
    "/{checklist_id}/sections/{section_id}",
    response_model=AdminSectionResponse,
    summary="Update Section",
    description="Updates section title, chapter code, ordering, and descriptive fields.",
)
def admin_update_section(
    checklist_id: UUID,
    section_id: UUID,
    request: AdminSectionUpdateRequest,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSectionResponse:
    section = update_section(db, checklist_id=checklist_id, section_id=section_id, payload=request)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
    return section


@router.delete(
    "/{checklist_id}/sections/{section_id}",
    response_model=dict[str, str],
    summary="Delete Section",
    description="Deletes a section from the checklist when no longer needed.",
)
def admin_delete_section(
    checklist_id: UUID,
    section_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_section(db, checklist_id=checklist_id, section_id=section_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="section_not_found")
    return {"message": "section_deleted"}


@router.patch(
    "/{checklist_id}/sections/reorder",
    response_model=list[AdminSectionResponse],
    summary="Reorder Sections",
    description="Updates the order of multiple sections for drag-and-drop functionality.",
)
def admin_reorder_sections(
    checklist_id: UUID,
    request: AdminSectionReorderRequest,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminSectionResponse]:
    import logging
    logger = logging.getLogger(__name__)
    
    # Log the incoming request for debugging
    logger.info(f"REORDER REQUEST - Checklist ID: {checklist_id}")
    logger.info(f"REORDER REQUEST - Section orders count: {len(request.section_orders)}")
    for i, item in enumerate(request.section_orders):
        logger.info(f"REORDER REQUEST - Section {i+1}: ID={item.section_id}, Order={item.order}")
    
    try:
        result = reorder_sections(db, checklist_id=checklist_id, section_orders=request.section_orders)
        logger.info(f"REORDER SUCCESS - Returned {len(result)} sections")
        return result
    except ValueError as exc:
        logger.error(f"REORDER ERROR - ValueError: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"REORDER ERROR - Unexpected error: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


@router.get(
    "/{checklist_id}/sections/{section_id}/questions",
    response_model=list[AdminQuestionResponse],
    summary="List Questions",
    description="Lists all checklist questions for the target section.",
)
def admin_list_questions(
    checklist_id: UUID,
    section_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> list[AdminQuestionResponse]:
    return list_questions(db, checklist_id=checklist_id, section_id=section_id)


@router.get(
    "/{checklist_id}/sections/{section_id}/questions/{question_id}",
    response_model=AdminQuestionResponse,
    summary="Get Question",
    description="Returns a specific checklist question with scoring and evidence rules.",
)
def admin_get_question(
    checklist_id: UUID,
    section_id: UUID,
    question_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionResponse:
    question = get_question(db, checklist_id=checklist_id, section_id=section_id, question_id=question_id)
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question_not_found")
    return question


@router.post(
    "/{checklist_id}/sections/{section_id}/questions",
    response_model=AdminQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Question",
    description="Creates a new question in a section with scoring mode, severity, and recommendation template.",
)
def admin_create_question(
    checklist_id: UUID,
    section_id: UUID,
    request: AdminQuestionCreateRequest,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionResponse:
    try:
        return create_question(db, checklist_id=checklist_id, section_id=section_id, payload=request)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch(
    "/{checklist_id}/sections/{section_id}/questions/{question_id}",
    response_model=AdminQuestionResponse,
    summary="Update Question",
    description="Updates question text, legal requirement, scoring behavior, and evidence constraints.",
)
def admin_update_question(
    checklist_id: UUID,
    section_id: UUID,
    question_id: UUID,
    request: AdminQuestionUpdateRequest,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionResponse:
    try:
        question = update_question(
            db,
            checklist_id=checklist_id,
            section_id=section_id,
            question_id=question_id,
            payload=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question_not_found")
    return question


@router.delete(
    "/{checklist_id}/sections/{section_id}/questions/{question_id}",
    response_model=dict[str, str],
    summary="Delete Question",
    description="Deletes a question entry from the section.",
)
def admin_delete_question(
    checklist_id: UUID,
    section_id: UUID,
    question_id: UUID,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    deleted = delete_question(db, checklist_id=checklist_id, section_id=section_id, question_id=question_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="question_not_found")
    return {"message": "question_deleted"}
