from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.assessment import Assessment
from app.models.report import Report, ReportStatus
from app.models.user import User, UserRole
from app.schemas.report import ReportResponse, CustomerReportDataResponse
from app.services.report import get_report_by_assessment, get_customer_report_data
from app.services.company_context import resolve_company_id, user_has_company_access
from app.utils.i18n import get_language_code

router = APIRouter(prefix="/customer/reports", tags=["customer-reports"])


@router.get(
    "/my-reports",
    response_model=list[ReportResponse],
    summary="List Customer's Reports",
    description="Returns all reports for the current customer's assessments. Only approved/published reports are included.",
)
def list_customer_reports(
    request: Request,
    company_id: UUID | None = Query(None, description="Optional company/tenant filter"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReportResponse]:
    """Get all reports for the current customer"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db)
    resolved_company_id = resolve_company_id(current_user, company_id)
    if not user_has_company_access(db, user=current_user, company_id=resolved_company_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers can access their reports")
    
    # Get all assessments for the customer
    assessment_query = select(Assessment).where(Assessment.user_id == current_user.id)
    if resolved_company_id is not None:
        assessment_query = assessment_query.where(Assessment.company_id == resolved_company_id)
    assessments = db.scalars(assessment_query).all()
    
    reports = []
    for assessment in assessments:
        try:
            report = get_report_by_assessment(db, assessment_id=assessment.id, lang_code=lang_code)
            # Only include approved or published reports
            if report.status in [ReportStatus.approved, ReportStatus.published]:
                reports.append(report)
        except HTTPException:
            # Skip assessments without reports
            continue
    
    return reports


@router.get(
    "/assessment/{assessment_id}",
    response_model=ReportResponse,
    summary="Get Report by Assessment",
    description="Returns the report for a specific assessment. Only available for approved/published reports.",
)
def get_customer_report_by_assessment(
    assessment_id: UUID,
    request: Request,
    company_id: UUID | None = Query(None, description="Optional company/tenant filter"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """Get report for a specific assessment"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db)
    resolved_company_id = resolve_company_id(current_user, company_id)
    
    # Verify the assessment belongs to the customer
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assessment not found"
        )
    if resolved_company_id is not None and assessment.company_id != resolved_company_id:
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
    company_id: UUID | None = Query(None, description="Optional company/tenant filter"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """Get specific report details"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db)
    resolved_company_id = resolve_company_id(current_user, company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if assessment is None or assessment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    if resolved_company_id is not None and assessment.company_id != resolved_company_id:
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
    company_id: UUID | None = Query(None, description="Optional company/tenant filter"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download PDF version of the report"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can download their reports"
        )
    
    lang_code = get_language_code(request, db)
    resolved_company_id = resolve_company_id(current_user, company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if assessment is None or assessment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    if resolved_company_id is not None and assessment.company_id != resolved_company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    # Only allow download of published reports
    if report.status != ReportStatus.published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report is not yet available for download"
        )
    
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
    company_id: UUID | None = Query(None, description="Optional company/tenant filter"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CustomerReportDataResponse:
    """Get comprehensive report data for PDF generation"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db)
    resolved_company_id = resolve_company_id(current_user, company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if assessment is None or assessment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    if resolved_company_id is not None and assessment.company_id != resolved_company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    
    # Only allow access to approved or published reports
    if report.status not in [ReportStatus.approved, ReportStatus.published]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report is not yet available for download"
        )
    
    return get_customer_report_data(db, report_id=report_id, company_id=resolved_company_id, lang_code=lang_code)


@router.get(
    "/{report_id}/preview",
    summary="Preview Report HTML",
    description="Returns HTML preview of the report for testing purposes.",
)
def preview_customer_report_html(
    report_id: UUID,
    request: Request,
    company_id: UUID | None = Query(None, description="Optional company/tenant filter"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview HTML version of the report"""
    if current_user.role != UserRole.customer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can access their reports"
        )
    
    lang_code = get_language_code(request, db)
    resolved_company_id = resolve_company_id(current_user, company_id)
    
    # Get the report
    from app.services.report import get_report
    report = get_report(db, report_id=report_id, lang_code=lang_code)
    
    # Verify the report belongs to the customer's assessment
    assessment = db.get(Assessment, report.assessment_id)
    if assessment is None or assessment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )
    if resolved_company_id is not None and assessment.company_id != resolved_company_id:
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
