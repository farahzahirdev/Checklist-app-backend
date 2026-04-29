from uuid import UUID
import base64
import io

from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles, require_admin_or_auditor_for_read, require_admin_only
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
    AdminQuestionReorderRequest,
    AdminSectionCreateRequest,
    AdminSectionListResponse,
    AdminSectionReorderRequest,
    AdminSectionUpdateRequest,
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
    reorder_questions,
    reorder_sections,
    update_checklist,
    update_question,
    update_section,
)
from app.schemas.bulk_checklist import (
    ColumnMapping,
    ColumnMappingResponse,
    VerifyMappingRequest,
    VerifyMappingResponse,
    BulkChecklistCreateRequest,
    BulkChecklistCreateResponse,
    BulkChecklistTaskResponse,
    BulkChecklistTaskStatusResponse,
)
from app.services.bulk_checklist import (
    verify_mapping,
    create_checklist_from_file,
)
from app.tasks.bulk_import import create_checklist_task
from app.celery_app import celery_app

router = APIRouter(prefix="/admin/checklists", tags=["admin-checklists"])


@router.get(
    "",
    response_model=AdminChecklistListResponse,
    summary="List Checklists",
    description="Admin and auditor list of all checklists available for publishing and assessment delivery.",
)
def admin_list_checklists(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for titles or law decree"),
    _admin=Depends(require_admin_or_auditor_for_read()),
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
    admin=Depends(require_admin_only()),
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
    _admin=Depends(require_admin_or_auditor_for_read()),
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
    admin=Depends(require_admin_only()),
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
    admin=Depends(require_admin_only()),
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
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    lang_code = "en"  # No request object, fallback to English or refactor for lang_code
    try:
        deleted = delete_checklist(db, checklist_id=checklist_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
        return {"message": translate("checklist_deleted", lang_code)}
    except ValueError as exc:
        # Handle foreign key constraint violations
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for section titles"),
    _admin=Depends(require_admin_or_auditor_for_read()),
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
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> AdminSectionResponse:
    lang_code = get_language_code(http_request, db)
    return create_section(
        db, checklist_id=checklist_id, payload=request, lang_code=lang_code
    )


@router.patch(
    "/{checklist_id}/sections/reorder",
    response_model=list[AdminSectionResponse],
    summary="Reorder Sections",
    description="Updates the order of multiple sections for drag-and-drop functionality.",
)
def admin_reorder_sections(
    checklist_id: UUID,
    request: AdminSectionReorderRequest,
    _admin=Depends(require_admin_only()),
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


@router.patch(
    "/{checklist_id}/sections/reorder/",
    response_model=list[AdminSectionResponse],
    summary="Reorder Sections (with trailing slash)",
    description="Updates the order of multiple sections for drag-and-drop functionality. Handles URLs with trailing slash.",
    include_in_schema=False,  # Hide from OpenAPI docs to avoid duplication
)
def admin_reorder_sections_trailing_slash(
    checklist_id: UUID,
    request: AdminSectionReorderRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> list[AdminSectionResponse]:
    # Redirect to the main endpoint to avoid code duplication
    return admin_reorder_sections(checklist_id, request, _admin, db)


@router.patch(
    "/{checklist_id}/sections/{section_id}/questions/reorder",
    response_model=list[AdminQuestionResponse],
    summary="Reorder Questions",
    description="Updates order of multiple questions for drag-and-drop functionality. Child questions cannot be ordered above their parent questions.",
)
def admin_reorder_questions(
    checklist_id: UUID,
    section_id: UUID,
    request: AdminQuestionReorderRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> list[AdminQuestionResponse]:
    import logging
    logger = logging.getLogger(__name__)
    
    # Log the incoming request for debugging
    logger.info(f"QUESTION REORDER REQUEST - Checklist ID: {checklist_id}, Section ID: {section_id}")
    logger.info(f"QUESTION REORDER REQUEST - Question orders count: {len(request.question_orders)}")
    for i, item in enumerate(request.question_orders):
        logger.info(f"QUESTION REORDER REQUEST - Question {i+1}: ID={item.question_id}, Order={item.order}")
    
    try:
        result = reorder_questions(db, checklist_id=checklist_id, section_id=section_id, question_orders=request.question_orders)
        logger.info(f"QUESTION REORDER SUCCESS - Returned {len(result)} questions")
        return result
    except ValueError as exc:
        logger.error(f"QUESTION REORDER ERROR - ValueError: {exc}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"QUESTION REORDER ERROR - Unexpected error: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error") from exc


@router.patch(
    "/{checklist_id}/sections/{section_id}/questions/reorder/",
    response_model=list[AdminQuestionResponse],
    summary="Reorder Questions (with trailing slash)",
    description="Updates order of multiple questions for drag-and-drop functionality. Child questions cannot be ordered above their parent questions. Handles URLs with trailing slash.",
    include_in_schema=False,  # Hide from OpenAPI docs to avoid duplication
)
def admin_reorder_questions_trailing_slash(
    checklist_id: UUID,
    section_id: UUID,
    request: AdminQuestionReorderRequest,
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> list[AdminQuestionResponse]:
    # Redirect to main endpoint to avoid code duplication
    return admin_reorder_questions(checklist_id, section_id, request, _admin, db)


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
    _admin=Depends(require_admin_only()),
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
    _admin=Depends(require_admin_only()),
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
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Search text for question text/code"),
    _admin=Depends(require_admin_or_auditor_for_read()),
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
    _admin=Depends(require_admin_or_auditor_for_read()),
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
    _admin=Depends(require_admin_only()),
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
    _admin=Depends(require_admin_only()),
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
    _admin=Depends(require_admin_only()),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    lang_code = "en"  # No request object, fallback to English or refactor for lang_code
    deleted = delete_question(
        db, checklist_id=checklist_id, section_id=section_id, question_id=question_id
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("question_not_found", lang_code))
    return {"message": translate("question_deleted", lang_code)}


# ============================================================================
# Bulk Import Routes
# ============================================================================

@router.get(
    "/bulk/template/mapping",
    response_model=ColumnMappingResponse,
    summary="Get Column Mapping Specification",
    description="Returns the column mapping template for Excel/CSV import.",
)
def get_column_mapping_spec(
    _admin=Depends(require_admin_or_auditor_for_read()),
) -> ColumnMappingResponse:
    """Get the column mapping specification template."""
    template = ColumnMapping(
        section_name_col="B",
        question_id_col="E",
        child_question_col="F",
        grandchild_question_col="G",
        legal_requirement_col="H",
        question_text_col="D",
        severity_col="I",
        explanation_col="J",
        expected_implementation_col="K",
        source_ref_col="C",
        guidance_score_4_col="L",
        guidance_score_3_col="M",
        guidance_score_2_col="N",
        guidance_score_1_col="O",
    )
    
    return ColumnMappingResponse(
        description=(
            "Standard mapping for checklist Excel import with two header rows. "
            "Row 1 contains grouped labels, and row 2 contains the actual section and question-id subcolumn labels. "
            "Use column letters for fixed positions or row-2 header values for matching."
        ),
        required_columns=[
            "section_name_col",
            "question_id_col",
            "legal_requirement_col",
            "question_text_col",
            "severity_col",
        ],
        optional_columns=[
            "child_question_col",
            "grandchild_question_col",
            "explanation_col",
            "expected_implementation_col",
            "source_ref_col",
            "guidance_score_4_col",
            "guidance_score_3_col",
            "guidance_score_2_col",
            "guidance_score_1_col",
        ],
        column_mapping_template=template,
        example_format={
            "section_name": "Governance & Management",
            "parent_question_id": "GOV-001",
            "parent_question_text": "Does the organization have a documented governance structure?",
            "child_question_id": "GOV-001.1",
            "grandchild_question_id": "GOV-001.1.1",
            "legal_requirement": "Article 5 of Regulation X",
            "severity": "High",
            "explanation": "Explain why this requirement is important.",
            "expected_implementation": "Implement a formal governance framework.",
            "source_ref": "ISO 27001:2022",
            "guidance_score_4": "Complete governance framework with clear roles",
            "guidance_score_3": "Documented but incomplete governance",
            "guidance_score_2": "Partial documentation of governance",
            "guidance_score_1": "No formal governance structure",
        },
    )


@router.get(
    "/bulk/template/download",
    summary="Download Sample Template",
    description="Downloads a sample Excel or CSV template for bulk import.",
)
def download_template(
    format: str = "csv",
    _admin=Depends(require_admin_or_auditor_for_read()),
):
    """Download sample template in CSV or XLSX format."""
    
    format_lower = format.lower()
    if format_lower not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Format must be 'csv' or 'xlsx'")
    
    # Sample data using a two-row header layout for import files.
    header_row_1 = [
        "#",
        "",
        "Source",
        "Paragraph Title",
        "Question id",
        "",
        "",
        "Legal Requirement",
        "Severity",
        "Explaination",
        "Expected Implementation",
        "Answers yes / 4 points",
        "Answers yes / 3 points",
        "Answers yes / 2 points",
        "Answers yes / 1 points",
        "Final score",
        "Add a note (for user)",
        "Upload evidence",
    ]
    header_row_2 = [
        "",
        "section",
        "",
        "",
        "1",
        "2",
        "3",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]

    sample_rows = [
        [
            "1",
            "Governance & Management",
            "ISO 27001",
            "Does the organization have a documented governance structure?",
            "GOV-001",
            "GOV-001.1",
            "GOV-001.1.1",
            "Article 5 of Regulation X",
            "High",
            "Detailed explanation for governance requirement.",
            "Implement a formal governance framework.",
            "Complete governance framework with clear roles",
            "Documented but incomplete governance",
            "Partial documentation of governance",
            "No formal governance structure",
            "4",
            "Add note if needed",
            "Evidence file",
        ],
        [
            "2",
            "Governance & Management",
            "Regulation X",
            "How does the organization ensure continuous compliance?",
            "GOV-002",
            None,
            None,
            "Ongoing monitoring requirement",
            "Medium",
            "Explanation for compliance monitoring.",
            "Establish monitoring procedures.",
            "Continuous automated monitoring",
            "Regular manual reviews",
            "Periodic reviews",
            "Ad-hoc reviews",
            "3",
            "User note example",
            "Evidence attachment",
        ],
    ]
    
    if format_lower == "csv":
        # Generate CSV with two header rows to reflect merged Excel header groups.
        output = io.StringIO()
        output.write(",".join(header_row_1) + "\n")
        output.write(",".join(header_row_2) + "\n")
        for row in sample_rows:
            escaped_row = [
                f'"{str(cell).replace(chr(34), chr(34) + chr(34))}"' if cell is not None else '""'
                for cell in row
            ]
            output.write(",".join(escaped_row) + "\n")
        
        content = output.getvalue().encode('utf-8')
        filename = "checklist_template.csv"
        media_type = "text/csv"
    else:  # xlsx
        try:
            import pandas as pd
        except ImportError:
            raise HTTPException(status_code=500, detail="pandas not installed")
        
        # Generate XLSX using pandas with a two-row header structure.

        columns = pd.MultiIndex.from_tuples([
            ("#", ""),
            ("", "section"),
            ("Source", ""),
            ("Paragraph Title", ""),
            ("Question id", "1"),
            ("Question id", "2"),
            ("Question id", "3"),
            ("Legal Requirement", ""),
            ("Severity", ""),
            ("Explaination", ""),
            ("Expected Implementation", ""),
            ("Answers yes / 4 points", ""),
            ("Answers yes / 3 points", ""),
            ("Answers yes / 2 points", ""),
            ("Answers yes / 1 points", ""),
            ("Final score", ""),
            ("Add a note (for user)", ""),
            ("Upload evidence", ""),
        ])
        df = pd.DataFrame(sample_rows, columns=columns)

        # Flatten MultiIndex columns for Excel export
        df.columns = [
            '_'.join([str(part) for part in col if part]) if isinstance(col, tuple) else str(col)
            for col in df.columns.values
        ]

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name='Template', index=False)
        
        content = output.getvalue()
        filename = "checklist_template.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/bulk/verify",
    response_model=VerifyMappingResponse,
    summary="Verify Column Mapping",
    description="Upload file and verify column mapping without creating data.",
)
def verify_column_mapping(
    request: VerifyMappingRequest,
    _admin=Depends(require_admin_only()),
) -> VerifyMappingResponse:
    """Verify column mapping by parsing file and showing preview."""
    try:
        if isinstance(request.file_content, str):
            try:
                file_content = base64.b64decode(request.file_content)
            except Exception:
                file_content = request.file_content.encode('utf-8')
        else:
            file_content = request.file_content
        
        response = verify_mapping(
            file_content=file_content,
            file_name=request.file_name,
            column_mapping=request.column_mapping,
            preview_rows=request.preview_rows,
        )
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Verification failed: {str(e)}"
        )


@router.post(
    "/bulk/create",
    response_model=BulkChecklistTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create Checklist from File",
    description="Queue file parsing and checklist creation as a background task.",
)
def create_from_file(
    request: BulkChecklistCreateRequest,
    admin=Depends(require_admin_only()),
) -> BulkChecklistTaskResponse:
    """Queue checklist creation by parsing uploaded Excel/CSV file in the background."""
    try:
        if isinstance(request.file_content, str):
            try:
                file_content = base64.b64decode(request.file_content)
            except Exception:
                file_content = request.file_content.encode("utf-8")
        else:
            file_content = request.file_content

        task = create_checklist_task.apply_async(
            args=[
                admin.id,
                base64.b64encode(file_content).decode("ascii"),
                request.file_name,
                request.column_mapping.model_dump(),
                request.checklist_title,
                request.checklist_description,
                request.checklist_type_code,
            ]
        )
        return BulkChecklistTaskResponse(
            task_id=str(task.id),
            status="pending",
            detail="Bulk checklist import task queued.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue bulk import task: {str(e)}"
        )


@router.get(
    "/bulk/tasks/{task_id}",
    response_model=BulkChecklistTaskStatusResponse,
    summary="Get Bulk Import Task Status",
    description="Returns current Celery task state and any completed result for bulk checklist import.",
)
def get_bulk_import_task_status(
    task_id: str,
    _admin=Depends(require_admin_or_auditor_for_read()),
) -> BulkChecklistTaskStatusResponse:
    async_result = celery_app.AsyncResult(task_id)
    state = async_result.state
    detail = "Task queued or waiting for worker execution."
    status_text = "pending"
    result = None
    error = None

    if state == "PENDING":
        detail = "Task is pending execution."
    elif state == "STARTED":
        detail = "Task has started processing."
        status_text = "started"
    elif state == "SUCCESS":
        payload = async_result.result or {}
        if isinstance(payload, dict):
            status_text = payload.get("status", "success")
            detail = payload.get("message", "Bulk import task completed.")
            result = BulkChecklistCreateResponse.model_validate(payload)
        else:
            status_text = "failed"
            error = "Unexpected task result format."
            detail = "Task completed with an invalid result payload."
    elif state in ("FAILURE", "RETRY"):
        status_text = "failed"
        error = str(async_result.result)
        detail = "Bulk import task failed."

    return BulkChecklistTaskStatusResponse(
        task_id=task_id,
        celery_state=state,
        status=status_text,
        detail=detail,
        result=result,
        error=error,
    )


@router.post(
    "/bulk/upload-and-verify",
    response_model=VerifyMappingResponse,
    summary="Upload and Verify File",
    description="Upload file as form-data and verify column mapping.",
)
async def upload_and_verify(
    file: UploadFile = File(...),
    section_col: str = "B",
    question_id_col: str = "C",
    child_question_col: str = "D",
    grandchild_question_col: str = "E",
    legal_req_col: str = "F",
    question_text_col: str = "H",
    severity_col: str = "I",
    _admin=Depends(require_admin_only()),
) -> VerifyMappingResponse:
    """Upload file as form-data and verify column mapping."""
    try:
        file_content = await file.read()
        
        mapping = ColumnMapping(
            section_name_col=section_col,
            question_id_col=question_id_col,
            child_question_col=child_question_col,
            grandchild_question_col=grandchild_question_col,
            legal_requirement_col=legal_req_col,
            question_text_col=question_text_col,
            severity_col=severity_col,
        )
        
        response = verify_mapping(
            file_content=file_content,
            file_name=file.filename or "upload",
            column_mapping=mapping,
            preview_rows=10,
        )
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload verification failed: {str(e)}"
        )
