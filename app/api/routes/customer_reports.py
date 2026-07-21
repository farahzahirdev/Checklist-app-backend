from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.report import Report, ReportStatus
from app.models.user import User, UserRole
from app.schemas.report import (
    ReportResponse,
    CustomerReportDataResponse,
    ReportPdfPasswordResponse,
    PaginatedCustomerReportsResponse,
)
from app.services.report import get_report_by_assessment, get_customer_report_data, get_report_pdf_password, get_report
from app.services.company_context import resolve_company_id, user_has_company_access
from app.utils.i18n import get_language_code

router = APIRouter(prefix="/customer/reports", tags=["customer-reports"])


def _assert_customer_report_company_access(
    db: Session,
    *,
    current_user: User,
    resolved_company_id: UUID | None,
) -> None:
    if not user_has_company_access(db, user=current_user, company_id=resolved_company_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can access their reports")


def _assessment_visible_to_customer(
    assessment: Assessment | None,
    *,
    current_user: User,
    resolved_company_id: UUID | None,
) -> bool:
    if assessment is None:
        return False
    if resolved_company_id is not None:
        return assessment.company_id == resolved_company_id
    return assessment.user_id == current_user.id


@router.get(
    "/my-reports",
    response_model=PaginatedCustomerReportsResponse,
    summary="List Customer's Reports",
    description="Returns paginated reports for the current customer's assessments. Only approved/published reports are included.",
)
def list_customer_reports(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=10, ge=1, le=100),
    sort_by: str = Query(default="final_pdf_published_at"),
    sort_order: str = Query(default="desc"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedCustomerReportsResponse:
    """Get paginated reports for the current customer"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)
    
    base_filters = [
        Report.status.in_([ReportStatus.approved, ReportStatus.published]),
    ]
    if resolved_company_id is not None:
        base_filters.append(Assessment.company_id == resolved_company_id)
    else:
        base_filters.append(Assessment.user_id == current_user.id)

    sort_col = {
        "final_pdf_published_at": Report.final_pdf_published_at,
        "approved_at": Report.approved_at,
        "draft_generated_at": Report.draft_generated_at,
        "created_at": Report.created_at,
    }.get(sort_by, Report.final_pdf_published_at)

    query = select(Report).join(Assessment, Report.assessment_id == Assessment.id).where(*base_filters)
    if sort_order == "asc":
        query = query.order_by(sort_col.asc().nulls_last())
    else:
        query = query.order_by(sort_col.desc().nulls_last())

    total = db.scalar(
        select(func.count(Report.id)).join(Assessment, Report.assessment_id == Assessment.id).where(*base_filters)
    ) or 0

    report_rows = db.scalars(query.offset(skip).limit(limit)).all()
    reports = [get_report(db, report_id=row.id, lang_code=lang_code) for row in report_rows]

    return PaginatedCustomerReportsResponse(reports=reports, total=total)


@router.get(
    "/assessment/{assessment_id}",
    response_model=ReportResponse,
    summary="Get Report by Assessment",
    description="Returns the report for a specific assessment. Only available for approved/published reports.",
)
def get_customer_report_by_assessment(
    assessment_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """Get report for a specific assessment"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)
    
    # Verify the assessment belongs to the customer
    assessment = db.get(Assessment, assessment_id)
    if not _assessment_visible_to_customer(
        assessment,
        current_user=current_user,
        resolved_company_id=resolved_company_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    
    # Get the report
    report = get_report_by_assessment(db, assessment_id=assessment_id, lang_code=lang_code)
    
    # Only allow access to approved or published reports
    if report.status not in [ReportStatus.approved, ReportStatus.published]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report is not yet available for download"
        )
    
    return report


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get Report Details",
    description="Returns detailed report information. Only available for approved/published reports.",
)
def get_customer_report(
    report_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """Get specific report details"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if not _assessment_visible_to_customer(
        assessment,
        current_user=current_user,
        resolved_company_id=resolved_company_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    # Only allow access to approved or published reports
    if report.status not in [ReportStatus.approved, ReportStatus.published]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report is not yet available for download"
        )
    
    return report


@router.get(
    "/{report_id}/download",
    summary="Download Report PDF",
    description="Generates and returns a PDF version of the report. Only available for published reports.",
)
def download_customer_report_pdf(
    report_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download PDF version of the report"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can download their reports"
        )
    
    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if not _assessment_visible_to_customer(
        assessment,
        current_user=current_user,
        resolved_company_id=resolved_company_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    from app.services.report import assert_customer_report_downloadable

    report_row = db.get(Report, report_id)
    if report_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    assert_customer_report_downloadable(report=report_row, assessment=assessment, lang_code=lang_code)

    # Generate PDF (will be implemented in the next step)
    from app.services.pdf_generator import generate_report_pdf
    pdf_content = generate_report_pdf(db, report_id=report_id, company_id=resolved_company_id, lang_code=lang_code)
    
    from fastapi.responses import Response
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=report_{report_id}.pdf"
        }
    )


@router.get(
    "/{report_id}/data",
    response_model=CustomerReportDataResponse,
    summary="Get Report Data for PDF Generation",
    description="Returns comprehensive report data including scores, findings, and summaries for PDF generation.",
)
def get_customer_report_data_endpoint(
    report_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerReportDataResponse:
    """Get comprehensive report data for PDF generation"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if not _assessment_visible_to_customer(
        assessment,
        current_user=current_user,
        resolved_company_id=resolved_company_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    # Only allow access to approved or published reports
    if report.status not in [ReportStatus.approved, ReportStatus.published]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report is not yet available for download"
        )
    
    return get_customer_report_data(db, report_id=report_id, company_id=resolved_company_id, lang_code=lang_code)


@router.get(
    "/{report_id}/pdf-password",
    response_model=ReportPdfPasswordResponse,
    summary="Get Report PDF Password",
    description="Returns the PDF password for the report owner when password protection is enabled.",
)
def get_customer_report_pdf_password(
    report_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportPdfPasswordResponse:
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports",
        )

    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)

    from app.services.report import get_report

    report = get_report(db, report_id=report_id, lang_code=lang_code)
    assessment = db.get(Assessment, report.assessment_id)
    if not _assessment_visible_to_customer(
        assessment,
        current_user=current_user,
        resolved_company_id=resolved_company_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return get_report_pdf_password(
        db,
        report_id=report_id,
        requesting_user=current_user,
        requesting_company_id=resolved_company_id,
        lang_code=lang_code,
    )


@router.get(
    "/{report_id}/preview",
    summary="Preview Report HTML",
    description="Returns HTML preview of the report for testing purposes.",
)
def preview_customer_report_html(
    report_id: UUID,
    request: Request,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview HTML version of the report"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db, current_user)
    resolved_company_id = resolve_company_id(current_user, None)
    _assert_customer_report_company_access(db, current_user=current_user, resolved_company_id=resolved_company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if not _assessment_visible_to_customer(
        assessment,
        current_user=current_user,
        resolved_company_id=resolved_company_id,
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    # Only allow access to approved or published reports
    if report.status not in [ReportStatus.approved, ReportStatus.published]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report is not yet available for preview"
        )
    
    # Generate HTML preview
    from app.services.pdf_generator import generate_report_html_preview
    html_content = generate_report_html_preview(db, report_id=report_id, company_id=resolved_company_id, lang_code=lang_code)
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)
