
import os
import asyncio
import importlib
import logging
from io import BytesIO
from uuid import UUID
from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateNotFound
from sqlalchemy.orm import Session
from playwright.async_api import async_playwright

from app.core.security import decrypt_secret
from app.models.report import Report, ReportStatus
from app.services.report import get_customer_report_data

logger = logging.getLogger(__name__)


def _load_pypdf() -> tuple[Any, Any]:
    try:
        module = importlib.import_module("pypdf")
        return module.PdfReader, module.PdfWriter
    except ImportError as exc:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="pypdf_package_not_installed") from exc


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
    logger.info(f"generate_report_pdf called with lang_code: {lang_code}")
    report_data = get_customer_report_data(db, report_id=report_id, company_id=company_id, lang_code=lang_code)
    if report_data.report_status != ReportStatus.published:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Report must be published before PDF generation")

    section_scores = [score.model_dump(mode='json') for score in report_data.section_scores]

    # Prepare SVG-based spider chart data (works better with PDF generation)
    import math
    n = len(section_scores) if section_scores else 3
    chart_type = "radar"  # Always use spider/radar chart

    # Extract labels and data for spider chart
    chart_labels = []
    chart_data = []
    
    for section in section_scores:
        # Handle both dict and object access
        if isinstance(section, dict):
            section_number = section.get('section_number', 1)
            section_title = section.get('section_title', 'Unknown')
            percentage = section.get('percentage', 0)
        else:
            section_number = getattr(section, 'section_number', 1)
            section_title = getattr(section, 'section_title', 'Unknown')
            percentage = getattr(section, 'percentage', 0)

        # Ensure percentage is numeric and reasonable
        try:
            percentage = float(percentage) if percentage is not None else 0.0
        except (ValueError, TypeError):
            percentage = 0.0

        # Clamp percentage to 0-100 range
        percentage = max(0.0, min(100.0, percentage))
        
        chart_labels.append(f"§{section_number}")
        chart_data.append(percentage)

    # Calculate SVG spider chart coordinates
    spider_chart_data = {
        'n': n,
        'labels': chart_labels,
        'data': chart_data
    }
    
    # Calculate grid levels (25%, 50%, 75%, 100%)
    grid_levels = []
    for level in [25, 50, 75, 100]:
        radius = 120 * (level / 100)
        level_points = []
        for i in range(n):
            angle = -1.5708 + (6.2832 * i / n)
            x = 190 + radius * math.cos(angle)
            y = 170 + radius * math.sin(angle)
            level_points.append(f"{x} {y}")
        grid_levels.append(level_points)
    
    # Calculate axis lines
    axis_lines = []
    for i in range(n):
        angle = -1.5708 + (6.2832 * i / n)
        x = 190 + 120 * math.cos(angle)
        y = 170 + 120 * math.sin(angle)
        axis_lines.append(f"{x},{y}")
    
    # Calculate label positions
    label_positions = []
    for i in range(n):
        angle = -1.5708 + (6.2832 * i / n)
        x = 190 + 140 * math.cos(angle)
        y = 170 + 140 * math.sin(angle)
        label_positions.append({
            'number': i + 1,
            'position': f"{x},{y}"
        })
    
    # Calculate data points
    data_points = []
    for i, percentage in enumerate(chart_data[:n]):
        angle = -1.5708 + (6.2832 * i / n)
        radius = 120 * (percentage / 100)
        x = 190 + radius * math.cos(angle)
        y = 170 + radius * math.sin(angle)
        data_points.append(f"{x},{y}")
    
    spider_chart_data['grid_levels'] = grid_levels
    spider_chart_data['axis_lines'] = axis_lines
    spider_chart_data['label_positions'] = label_positions
    spider_chart_data['data_points'] = data_points
    
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    if not os.path.exists(template_dir):
        logger.error(f"Template directory not found: {template_dir}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Report template not found")

    # Select template based on language
    template_name = f'customer_report_{lang_code}.html'
    logger.info(f"Attempting to load template: {template_name}")
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        # Try language-specific template first, fall back to English
        try:
            template = env.get_template(template_name)
            logger.info(f"Successfully loaded template: {template_name}")
        except TemplateNotFound:
            logger.warning(f"Template {template_name} not found, falling back to English template")
            template = env.get_template('customer_report_en.html')
    except Exception as e:
        logger.error(f"Failed to load template: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to load template: {str(e)}")

    try:
        logger.info("Starting template rendering...")
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
            checklist_type_name=report_data.checklist_type_name,
            audit_type=report_data.checklist_type_name or report_data.checklist_title,
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
            section_scores=section_scores,
            spider_chart_data=spider_chart_data,
            chart_type=chart_type,
            chapter_data=report_data.chapter_data,
            domain_data=report_data.domain_data,
            findings=report_data.findings,
            section_summaries=report_data.section_summaries,
            public_suggestions=report_data.public_suggestions,
            management_summary=report_data.management_summary,
            generated_at=report_data.generated_at,
            approved_at=report_data.approved_at,
            published_at=report_data.published_at,
        )
        logger.info("Template rendering completed successfully")
    except Exception as e:
        logger.error(f"Template rendering failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Template rendering failed: {str(e)}")

    try:
        logger.info("Starting PDF generation with Playwright...")
        pdf_bytes = asyncio.run(_generate_pdf_with_playwright(html_content))
        logger.info("PDF generation completed successfully")
    except Exception as e:
        logger.error(f"PDF generation with Playwright failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF generation failed: {str(e)}")

    try:
        logger.info("Checking for PDF password encryption...")
        report = db.get(Report, report_id)
        if report and report.final_pdf_password_encrypted:
            PdfReader, PdfWriter = _load_pypdf()

            user_password = decrypt_secret(report.final_pdf_password_encrypted)
            reader = PdfReader(BytesIO(pdf_bytes))
            writer = PdfWriter()
            for page in reader.pages:
                writer.add_page(page)
            writer.encrypt(user_password)

            encrypted_stream = BytesIO()
            writer.write(encrypted_stream)
            return encrypted_stream.getvalue()

        return pdf_bytes
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate PDF: {str(e)}")


def generate_report_html_preview(db: Session, *, report_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> str:
    template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
    # Select template based on language
    template_name = f'customer_report_{lang_code}.html'
    logger.info(f"Attempting to load template: {template_name}")
    env = Environment(loader=FileSystemLoader(template_dir))
    try:
        # Try language-specific template first, fall back to English
        try:
            template = env.get_template(template_name)
            print(f"Successfully loaded template: {template_name}")
        except TemplateNotFound:
            print(f"Template {template_name} not found, falling back to English template")
            template = env.get_template('customer_report_en.html')
        report_data = get_customer_report_data(db, report_id=report_id, company_id=company_id, lang_code=lang_code)
        section_scores = [score.model_dump(mode='json') for score in report_data.section_scores]

        # Pre-calculate chart data
        import math
        n = len(section_scores) if section_scores else 3
        chart_type = "radar"  # Always use spider/radar chart

        spider_chart_data = {
            'n': n,
            'grid_levels': [],
            'axis_lines': [],
            'labels': [],
            'data_points': []
        }

        # Calculate grid levels (25%, 50%, 75%, 100%)
        for level in [25, 50, 75, 100]:
            radius = 120 * (level / 100)
            level_points = []
            for i in range(n):
                angle = -1.5708 + (6.2832 * i / n)
                x = 190 + radius * math.cos(angle)
                y = 170 + radius * math.sin(angle)
                level_points.append(f"{x} {y}")
            spider_chart_data['grid_levels'].append(level_points)

        # Calculate axis lines
        for i in range(n):
            angle = -1.5708 + (6.2832 * i / n)
            x = 190 + 120 * math.cos(angle)
            y = 170 + 120 * math.sin(angle)
            spider_chart_data['axis_lines'].append(f"{x},{y}")

        # Calculate labels
        for i in range(n):
            angle = -1.5708 + (6.2832 * i / n)
            x = 190 + 140 * math.cos(angle)
            y = 170 + 140 * math.sin(angle)
            spider_chart_data['labels'].append({
                'number': i + 1,
                'position': f"{x},{y}"
            })

        # Calculate data points
        for i, section in enumerate(section_scores[:n]):
            angle = -1.5708 + (6.2832 * i / n)
            # Handle both dict and object access
            if isinstance(section, dict):
                percentage = section.get('percentage', 0)
            else:
                percentage = getattr(section, 'percentage', 0)

            # Ensure percentage is numeric and reasonable
            try:
                percentage = float(percentage) if percentage is not None else 0.0
            except (ValueError, TypeError):
                percentage = 0.0

            # Clamp percentage to 0-100 range
            percentage = max(0.0, min(100.0, percentage))

            radius = 120 * (percentage / 100)
            x = 190 + radius * math.cos(angle)
            y = 170 + radius * math.sin(angle)
            spider_chart_data['data_points'].append(f"{x},{y}")

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
            checklist_type_name=report_data.checklist_type_name,
            audit_type=report_data.checklist_type_name or report_data.checklist_title,
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
            section_scores=section_scores,
            spider_chart_data=spider_chart_data,
            chart_type=chart_type,
            chapter_data=report_data.chapter_data,
            domain_data=report_data.domain_data,
            findings=report_data.findings,
            section_summaries=report_data.section_summaries,
            public_suggestions=report_data.public_suggestions,
            management_summary=report_data.management_summary,
            generated_at=report_data.generated_at,
            approved_at=report_data.approved_at,
            published_at=report_data.published_at,
        )
        return html_content
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate HTML preview: {str(e)}")
