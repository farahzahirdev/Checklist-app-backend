from uuid import UUID

from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.admin_checklist import (
    AdminChecklistCreateRequest,
    AdminChecklistListResponse,
    AdminChecklistResponse,
    AdminChecklistUpdateRequest,
    AdminQuestionCreateRequest,
    AdminQuestionListResponse,
    AdminQuestionResponse,
    AdminQuestionUpdateRequest,
    AdminSectionCreateRequest,
    AdminSectionListResponse,
    AdminSectionResponse,
    AdminSectionUpdateRequest,
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
    update_checklist,
    update_question,
    update_section,
)

router = APIRouter(prefix="/admin/checklists", tags=["admin-checklists"])


@router.get(
    "",
    response_model=AdminChecklistListResponse,
    summary="List Checklists",
    description="Admin-only list of all checklists available for publishing and assessment delivery.",
)
def admin_list_checklists(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for titles or law decree"),
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistListResponse:
    lang_code = get_language_code(request, db)
    total, items = list_checklists(
        db,
        lang_code=lang_code,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
    )
    return {"total": total, "checklists": items, "skip": skip, "limit": limit}


@router.post(
    "",
    response_model=AdminChecklistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Checklist",
    description="Creates a new checklist draft including metadata, version, and access configuration.",
)
def admin_create_checklist(
    request: AdminChecklistCreateRequest,
    http_request: Request,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    lang_code = get_language_code(http_request, db)
    return create_checklist(db, actor=admin, payload=request, lang_code=lang_code)


@router.get(
    "/{checklist_id}",
    response_model=AdminChecklistResponse,
    summary="Get Checklist",
    description="Returns a single checklist with its current status and editable properties.",
)
def admin_get_checklist(
    checklist_id: UUID,
    request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    lang_code = get_language_code(request, db)
    checklist = get_checklist(db, checklist_id=checklist_id, lang_code=lang_code)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
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
    http_request: Request,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    lang_code = get_language_code(http_request, db)
    checklist = update_checklist(
        db, actor=admin, checklist_id=checklist_id, payload=request, lang_code=lang_code
    )
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
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
    http_request: Request,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminChecklistResponse:
    lang_code = get_language_code(http_request, db)
    checklist = publish_checklist(
        db, actor=admin, checklist_id=checklist_id, payload=request, lang_code=lang_code
    )
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
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
    lang_code = "en"  # No request object, fallback to English or refactor for lang_code
    deleted = delete_checklist(db, checklist_id=checklist_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
    return {"message": translate("checklist_deleted", lang_code)}


@router.get(
    "/{checklist_id}/sections",
    response_model=AdminSectionListResponse,
    summary="List Sections",
    description="Lists all sections under the specified checklist in display order.",
)
def admin_list_sections(
    checklist_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for section titles"),
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSectionListResponse:
    lang_code = get_language_code(request, db)
    total, items = list_sections(
        db,
        checklist_id=checklist_id,
        lang_code=lang_code,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
    )
    return {"total": total, "sections": items, "skip": skip, "limit": limit}


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
    http_request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSectionResponse:
    lang_code = get_language_code(http_request, db)
    return create_section(
        db, checklist_id=checklist_id, payload=request, lang_code=lang_code
    )


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
    http_request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminSectionResponse:
    lang_code = get_language_code(http_request, db)
    section = update_section(
        db, checklist_id=checklist_id, section_id=section_id, payload=request, lang_code=lang_code
    )
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("section_not_found", lang_code))
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
    lang_code = "en"  # No request object, fallback to English or refactor for lang_code
    deleted = delete_section(db, checklist_id=checklist_id, section_id=section_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("section_not_found", lang_code))
    return {"message": translate("section_deleted", lang_code)}


@router.get(
    "/{checklist_id}/sections/{section_id}/questions",
    response_model=AdminQuestionListResponse,
    summary="List Questions",
    description="Lists all checklist questions for the target section.",
)
def admin_list_questions(
    checklist_id: UUID,
    section_id: UUID,
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for question text/code"),
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionListResponse:
    lang_code = get_language_code(request, db)
    total, items = list_questions(
        db,
        checklist_id=checklist_id,
        section_id=section_id,
        lang_code=lang_code,
        skip=skip,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
    )
    return {"total": total, "questions": items, "skip": skip, "limit": limit}


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
    request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionResponse:
    lang_code = get_language_code(request, db)
    question = get_question(
        db, checklist_id=checklist_id, section_id=section_id, question_id=question_id, lang_code=lang_code
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("question_not_found", lang_code))
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
    http_request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionResponse:
    lang_code = get_language_code(http_request, db)
    try:
        return create_question(
            db, checklist_id=checklist_id, section_id=section_id, payload=request, lang_code=lang_code
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate(str(exc), lang_code)) from exc


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
    http_request: Request,
    _admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> AdminQuestionResponse:
    lang_code = get_language_code(http_request, db)
    try:
        question = update_question(
            db,
            checklist_id=checklist_id,
            section_id=section_id,
            question_id=question_id,
            payload=request,
            lang_code=lang_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate(str(exc), lang_code)) from exc
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("question_not_found", lang_code))
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
    lang_code = "en"  # No request object, fallback to English or refactor for lang_code
    deleted = delete_question(
        db, checklist_id=checklist_id, section_id=section_id, question_id=question_id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("question_not_found", lang_code))
    return {"message": translate("question_deleted", lang_code)}
