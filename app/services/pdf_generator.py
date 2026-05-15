import os
import asyncio
from uuid import UUID
from datetime import datetime

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright

from app.models.report import ReportStatus
from app.services.report import get_customer_report_data


async def _generate_pdf_with_playwright(html_content: str) -> bytes:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.set_content(html_content, wait_until="domcontentloaded", timeout=60000)
            await page.emulate_media(media="print")
            await asyncio.sleep(2)

            footer_html = """
            <div style="width:100%;font-size:10px;padding:0 12px;color:#6b7280;display:flex;justify-content:space-between;font-family:Arial, sans-serif;">
                <span>Compliance Assessment Report</span>
                <span style="font-variant-numeric: tabular-nums;"><span class="pageNumber"></span>/<span class="totalPages"></span></span>
            </div>
            """

            pdf_bytes = await page.pdf(
                format="A4",
                print_background=True,
                display_header_footer=True,
                header_template="<div></div>",
                footer_template=footer_html,
                margin={"top": "20mm", "bottom": "25mm", "left": "10mm", "right": "10mm"},
            )
            return pdf_bytes
        finally:
            await browser.close()


def generate_report_pdf(db: Session, *, report_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> bytes:
    report_data = get_customer_report_data(db, report_id=report_id, company_id=company_id, lang_code=lang_code)
    if report_data.report_status != ReportStatus.published:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Report must be published before PDF generation")

    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    if not os.path.exists(template_dir):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Report template not found")

    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        template = env.get_template('customer_report.html')
        html_content = template.render(
            report_id=report_data.report_id,
            report_uuid=report_data.report_uuid,
            customer_name=report_data.customer_name,
            customer_email=report_data.customer_email,
            company_name=report_data.company_name,
            company_website=report_data.company_website,
            company_industry=report_data.company_industry,
            company_size=report_data.company_size,
            company_region=report_data.company_region,
            company_country=report_data.company_country,
            company_description=report_data.company_description,
            checklist_title=report_data.checklist_title,
            assessment_date=report_data.assessment_date,
            report_status=report_data.report_status,
            overall_score=report_data.overall_score,
            max_possible_score=report_data.max_possible_score,
            total_score_percentage=report_data.total_score_percentage,
            completion_percentage=report_data.completion_percentage,
            total_questions=report_data.total_questions,
            answered_questions=report_data.answered_questions,
            standard_covered_all=report_data.standard_covered_all,
            question_score_distribution=report_data.question_score_distribution,
            section_scores=report_data.section_scores,
            chapter_data=report_data.chapter_data,
            domain_data=report_data.domain_data,
            findings=report_data.findings,
            section_summaries=report_data.section_summaries,
            public_suggestions=report_data.public_suggestions,
            generated_at=report_data.generated_at,
            approved_at=report_data.approved_at,
            published_at=report_data.published_at,
        )

        pdf_bytes = asyncio.run(_generate_pdf_with_playwright(html_content))
        return pdf_bytes
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate PDF: {str(e)}")


def generate_report_html_preview(db: Session, *, report_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> str:
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        template = env.get_template('customer_report.html')
        report_data = get_customer_report_data(db, report_id=report_id, company_id=company_id, lang_code=lang_code)
        html_content = template.render(
            report_id=report_data.report_id,
            report_uuid=report_data.report_uuid,
            customer_name=report_data.customer_name,
            customer_email=report_data.customer_email,
            company_name=report_data.company_name,
            company_website=report_data.company_website,
            company_industry=report_data.company_industry,
            company_size=report_data.company_size,
            company_region=report_data.company_region,
            company_country=report_data.company_country,
            company_description=report_data.company_description,
            checklist_title=report_data.checklist_title,
            assessment_date=report_data.assessment_date,
            report_status=report_data.report_status,
            overall_score=report_data.overall_score,
            max_possible_score=report_data.max_possible_score,
            total_score_percentage=report_data.total_score_percentage,
            completion_percentage=report_data.completion_percentage,
            total_questions=report_data.total_questions,
            answered_questions=report_data.answered_questions,
            standard_covered_all=report_data.standard_covered_all,
            question_score_distribution=report_data.question_score_distribution,
            section_scores=report_data.section_scores,
            chapter_data=report_data.chapter_data,
            domain_data=report_data.domain_data,
            findings=report_data.findings,
            section_summaries=report_data.section_summaries,
            public_suggestions=report_data.public_suggestions,
            generated_at=report_data.generated_at,
            approved_at=report_data.approved_at,
            published_at=report_data.published_at,
        )
        return html_content
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate HTML preview: {str(e)}")
