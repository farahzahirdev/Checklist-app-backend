from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles, get_current_user
from app.db.session import get_db
from app.models.user import UserRole
from app.utils.i18n import get_language_code
from app.schemas.report import (
    GenerateDraftReportRequest,
    PublishReportRequest,
    ReportFindingItem,
    ReportResponse,
    ReportSummaryItem,
    ReviewActionRequest,
    UpsertReportSummaryRequest,
)
from app.services.report import (
    approve_report,
    generate_draft_report,
    get_report,
    get_report_by_assessment,
    list_report_findings,
    list_report_summaries,
    publish_report,
    request_changes,
    start_review,
    upsert_report_summary,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post(
    "/draft",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Draft Report",
    description=(
        "Creates the first report draft for a submitted assessment. "
        "This endpoint scans low-confidence answers and creates initial findings. "
        "If a report already exists for the assessment, the existing report is returned."
    ),
)
def generate_draft_report_route(
    request: Request,
    payload: GenerateDraftReportRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return generate_draft_report(db, assessment_id=payload.assessment_id, actor=admin, lang_code=lang_code)


@router.get(
    "/",
    response_model=dict[str, Any],
    summary="List All Reports",
    description="Returns all reports with optional status filtering and pagination.",
)
def list_reports_route(
    request: Request,
    status: str | None = None,
    skip: int = 0,
    limit: int = 50,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.report import list_reports
    lang_code = get_language_code(request, db)
    return list_reports(db, status=status, skip=skip, limit=limit, lang_code=lang_code)


@router.get(
    "/assessment/{assessment_id}",
    response_model=ReportResponse,
    summary="Get Report By Assessment",
    description="Fetches the report currently linked to a specific assessment ID.",
)
def get_report_by_assessment_route(
    assessment_id: UUID,
    request: Request,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return get_report_by_assessment(db, assessment_id=assessment_id, lang_code=lang_code)


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get Report",
    description="Returns report lifecycle status, timestamps, and aggregate counters for findings and summaries.",
)
def get_report_route(
    report_id: UUID,
    request: Request,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return get_report(db, report_id=report_id, lang_code=lang_code)


@router.post(
    "/{report_id}/publish",
    response_model=ReportResponse,
    summary="Publish Final Report",
    description=(
        "Publishes the approved report by attaching final PDF storage location and marking the report as published. "
        "This endpoint enforces approval-before-publish."
    ),
)
def publish_report_route(
    report_id: UUID,
    request: Request,
    payload: PublishReportRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return publish_report(db, report_id=report_id, actor=admin, final_pdf_storage_key=payload.final_pdf_storage_key, lang_code=lang_code)


# Auditor and Admin Review Endpoints
@router.post(
    "/{report_id}/review/start",
    response_model=ReportResponse,
    summary="Start Review",
    description=(
        "Moves a draft report into under-review state and records who started the review. "
        "Both admins and auditors can start reviews."
    ),
)
def start_review_route(
    report_id: UUID,
    request: Request,
    payload: ReviewActionRequest,
    reviewer=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return start_review(db, report_id=report_id, actor=reviewer, payload=payload, lang_code=lang_code)


@router.post(
    "/{report_id}/review/request-changes",
    response_model=ReportResponse,
    summary="Request Report Changes",
    description="Marks a report as changes-requested and stores a review note for the authoring round.",
)
def request_changes_route(
    report_id: UUID,
    request: Request,
    payload: ReviewActionRequest,
    reviewer=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return request_changes(db, report_id=report_id, actor=reviewer, payload=payload, lang_code=lang_code)


@router.post(
    "/{report_id}/summaries",
    response_model=ReportSummaryItem,
    summary="Create Or Update Section Summary",
    description=(
        "Creates or updates narrative summary text for a section or chapter in the report. "
        "Summaries are used in the final PDF narrative and tracked in review events."
    ),
)
def upsert_summary_route(
    report_id: UUID,
    request: Request,
    payload: UpsertReportSummaryRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportSummaryItem:
    lang_code = get_language_code(request, db)
    return upsert_report_summary(db, report_id=report_id, actor=admin, payload=payload, lang_code=lang_code)


@router.get(
    "/{report_id}/summaries",
    response_model=list[ReportSummaryItem],
    summary="List Section Summaries",
    description="Returns all saved report summaries ordered by last update time (newest first).",
)
def list_summaries_route(
    report_id: UUID,
    request: Request,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> list[ReportSummaryItem]:
    lang_code = get_language_code(request, db)
    return list_report_summaries(db, report_id=report_id, lang_code=lang_code)


@router.get(
    "/{report_id}/findings",
    response_model=list[ReportFindingItem],
    summary="List Report Findings",
    description="Returns generated findings from assessment answers used to compose the report's risk section.",
)
def list_findings_route(
    report_id: UUID,
    request: Request,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> list[ReportFindingItem]:
    lang_code = get_language_code(request, db)
    return list_report_findings(db, report_id=report_id, lang_code=lang_code)


@router.post(
    "/{report_id}/approve",
    response_model=ReportResponse,
    summary="Approve Report",
    description="Approves a report for publication and stores reviewer approval metadata.",
)
def approve_report_route(
    report_id: UUID,
    request: Request,
    payload: ReviewActionRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return approve_report(db, report_id=report_id, actor=admin, payload=payload, lang_code=lang_code)


@router.post(
    "/{report_id}/publish",
    response_model=ReportResponse,
    summary="Publish Final Report",
    description=(
        "Publishes the approved report by attaching final PDF storage location and marking the report as published. "
        "This endpoint enforces approval-before-publish."
    ),
)
def publish_report_route(
    report_id: UUID,
    request: Request,
    payload: PublishReportRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    lang_code = get_language_code(request, db)
    return publish_report(db, report_id=report_id, actor=admin, final_pdf_storage_key=payload.final_pdf_storage_key, lang_code=lang_code)
