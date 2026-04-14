from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import require_roles
from app.db.session import get_db
from app.models.user import UserRole
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
    request: GenerateDraftReportRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return generate_draft_report(db, assessment_id=request.assessment_id, actor=admin)


@router.get(
    "/assessment/{assessment_id}",
    response_model=ReportResponse,
    summary="Get Report By Assessment",
    description="Fetches the report currently linked to a specific assessment ID.",
)
def get_report_by_assessment_route(
    assessment_id: UUID,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return get_report_by_assessment(db, assessment_id=assessment_id)


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get Report",
    description="Returns report lifecycle status, timestamps, and aggregate counters for findings and summaries.",
)
def get_report_route(
    report_id: UUID,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return get_report(db, report_id=report_id)


@router.post(
    "/{report_id}/review/start",
    response_model=ReportResponse,
    summary="Start Review",
    description=(
        "Moves a draft report into under-review state and records who started the review. "
        "Use this when an admin begins formal report QA."
    ),
)
def start_review_route(
    report_id: UUID,
    request: ReviewActionRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return start_review(db, report_id=report_id, actor=admin, payload=request)


@router.post(
    "/{report_id}/review/request-changes",
    response_model=ReportResponse,
    summary="Request Report Changes",
    description="Marks a report as changes-requested and stores a review note for the authoring round.",
)
def request_changes_route(
    report_id: UUID,
    request: ReviewActionRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return request_changes(db, report_id=report_id, actor=admin, payload=request)


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
    request: UpsertReportSummaryRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportSummaryItem:
    return upsert_report_summary(db, report_id=report_id, actor=admin, payload=request)


@router.get(
    "/{report_id}/summaries",
    response_model=list[ReportSummaryItem],
    summary="List Section Summaries",
    description="Returns all saved report summaries ordered by last update time (newest first).",
)
def list_summaries_route(
    report_id: UUID,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> list[ReportSummaryItem]:
    return list_report_summaries(db, report_id=report_id)


@router.get(
    "/{report_id}/findings",
    response_model=list[ReportFindingItem],
    summary="List Report Findings",
    description="Returns generated findings from assessment answers used to compose the report's risk section.",
)
def list_findings_route(
    report_id: UUID,
    _admin=Depends(require_roles(UserRole.admin, UserRole.auditor)),
    db: Session = Depends(get_db),
) -> list[ReportFindingItem]:
    return list_report_findings(db, report_id=report_id)


@router.post(
    "/{report_id}/approve",
    response_model=ReportResponse,
    summary="Approve Report",
    description="Approves a report for publication and stores reviewer approval metadata.",
)
def approve_report_route(
    report_id: UUID,
    request: ReviewActionRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return approve_report(db, report_id=report_id, actor=admin, payload=request)


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
    request: PublishReportRequest,
    admin=Depends(require_roles(UserRole.admin)),
    db: Session = Depends(get_db),
) -> ReportResponse:
    return publish_report(db, report_id=report_id, actor=admin, final_pdf_storage_key=request.final_pdf_storage_key)
