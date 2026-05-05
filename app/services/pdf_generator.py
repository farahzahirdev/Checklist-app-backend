import os
import tempfile
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, Template
from sqlalchemy.orm import Session
import weasyprint

from app.models.report import ReportStatus
from app.services.report import get_customer_report_data


def generate_report_pdf(db: Session, *, report_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> bytes:
    """Generate PDF report from HTML template"""
    
    # Get comprehensive report data
    report_data = get_customer_report_data(db, report_id=report_id, company_id=company_id, lang_code=lang_code)
    
    # Verify report is published
    if report_data.report_status != ReportStatus.published:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Report must be published before PDF generation"
        )
    
    # Get template path
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    if not os.path.exists(template_dir):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Report template not found"
        )
    
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(template_dir))
    
    try:
        # Load template
        template = env.get_template('customer_report.html')
        
        # Render HTML with data
        html_content = template.render(
            customer_name=report_data.customer_name,
            customer_email=report_data.customer_email,
            checklist_title=report_data.checklist_title,
            assessment_date=report_data.assessment_date,
            report_status=report_data.report_status,
            overall_score=report_data.overall_score,
            max_possible_score=report_data.max_possible_score,
            completion_percentage=report_data.completion_percentage,
            section_scores=report_data.section_scores,
            chapter_data=report_data.chapter_data,
            findings=report_data.findings,
            section_summaries=report_data.section_summaries,
            public_suggestions=report_data.public_suggestions,
            generated_at=report_data.generated_at,
            approved_at=report_data.approved_at,
            published_at=report_data.published_at,
        )
        
        # Generate PDF using WeasyPrint
        pdf_document = weasyprint.HTML(string=html_content)
        pdf_bytes = pdf_document.write_pdf()
        
        return pdf_bytes
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate PDF: {str(e)}"
        )


def generate_report_html_preview(db: Session, *, report_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> str:
    """Generate HTML preview of report (for testing/debugging)"""
    
    # Get comprehensive report data
    report_data = get_customer_report_data(db, report_id=report_id, company_id=company_id, lang_code=lang_code)
    
    # Get template path
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    
    try:
        # Load template
        template = env.get_template('customer_report.html')
        
        # Render HTML with data
        html_content = template.render(
            customer_name=report_data.customer_name,
            customer_email=report_data.customer_email,
            checklist_title=report_data.checklist_title,
            assessment_date=report_data.assessment_date,
            report_status=report_data.report_status,
            overall_score=report_data.overall_score,
            max_possible_score=report_data.max_possible_score,
            completion_percentage=report_data.completion_percentage,
            section_scores=report_data.section_scores,
            chapter_data=report_data.chapter_data,
            findings=report_data.findings,
            section_summaries=report_data.section_summaries,
            public_suggestions=report_data.public_suggestions,
            generated_at=report_data.generated_at,
            approved_at=report_data.approved_at,
            published_at=report_data.published_at,
        )
        
        return html_content
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate HTML preview: {str(e)}"
        )
