#!/usr/bin/env python3
"""Generate a sample PDF using the report template and Playwright PDF generator.

Run this from the repo's apps/api folder:
    python scripts/generate_sample_pdf.py

Output will be written to `test_output/report_sample.pdf`.
"""
import asyncio
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

from jinja2 import Environment, FileSystemLoader

from app.services import pdf_generator as pdf_mod


def make_fake_report():
    import uuid
    rid = uuid.uuid4()
    return SimpleNamespace(
        report_id=rid,
        report_uuid=str(rid),
        customer_name="ACME Corp",
        customer_email="contact@acme.example",
        company_name="ACME Corp",
        company_website="https://acme.example",
        company_industry="Manufacturing",
        company_size="100-250",
        company_region="NA",
        company_country="US",
        company_description="Sample company",
        checklist_title="ACME Compliance Assessment",
        assessment_date=datetime(2026, 5, 14),
        report_status=pdf_mod.ReportStatus.published,
        overall_score=78.4,
        max_possible_score=100,
        total_score_percentage=78.4,
        completion_percentage=91.2,
        total_questions=48,
        answered_questions=44,
        standard_covered_all=True,
        question_score_distribution=[],
        section_scores=[
            {"section_name": "Governance", "percentage": 82},
            {"section_name": "Operations", "percentage": 68},
            {"section_name": "Access Control", "percentage": 74},
            {"section_name": "Incident Response", "percentage": 61},
        ],
        chapter_data=[
            {"chapter_code": "CH-01", "title": "Chapter 1", "percentage": 75, "score": 7, "max_score": 10, "findings_count": 2},
            {"chapter_code": "CH-02", "title": "Chapter 2", "percentage": 64, "score": 6, "max_score": 10, "findings_count": 2},
        ],
        domain_data=[],
        findings=[
            {"priority": "high", "question_text": "Critical missing control", "recommendation": "Implement control X"},
            {"priority": "medium", "question_text": "Process gap in review cadence", "recommendation": "Add monthly review checkpoints"},
        ],
        section_summaries=[
            {"chapter_code": "CH-01", "summary_text": "Summary for chapter 1"},
            {"chapter_code": "CH-02", "summary_text": "Summary for chapter 2"},
        ],
        public_suggestions=[
            {"suggestion_text": "Do this next"},
            {"suggestion_text": "Add owner and timeline for remediation"},
        ],
        generated_at=datetime(2026, 5, 14),
        approved_at=datetime(2026, 5, 14),
        published_at=datetime(2026, 5, 14),
    )


def render_template(report):
    TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "app" / "templates"
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template('customer_report.html')
    html = template.render(
        report_id=report.report_id,
        report_uuid=report.report_uuid,
        customer_name=report.customer_name,
        customer_email=report.customer_email,
        company_name=report.company_name,
        company_website=report.company_website,
        company_industry=report.company_industry,
        company_size=report.company_size,
        company_region=report.company_region,
        company_country=report.company_country,
        company_description=report.company_description,
        checklist_title=report.checklist_title,
        assessment_date=report.assessment_date,
        report_status=report.report_status,
        overall_score=report.overall_score,
        max_possible_score=report.max_possible_score,
        total_score_percentage=report.total_score_percentage,
        completion_percentage=report.completion_percentage,
        total_questions=report.total_questions,
        answered_questions=report.answered_questions,
        standard_covered_all=report.standard_covered_all,
        question_score_distribution=report.question_score_distribution,
        section_scores=report.section_scores,
        chapter_data=report.chapter_data,
        domain_data=report.domain_data,
        findings=report.findings,
        section_summaries=report.section_summaries,
        public_suggestions=report.public_suggestions,
        generated_at=report.generated_at,
        approved_at=report.approved_at,
        published_at=report.published_at,
    )
    return html


def main():
    out_dir = Path("test_output")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "report_sample.pdf"

    report = make_fake_report()
    html = render_template(report)

    pdf_bytes = asyncio.run(pdf_mod._generate_pdf_with_playwright(html))
    out_path.write_bytes(pdf_bytes)
    print(f"Wrote sample PDF: {out_path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    main()
