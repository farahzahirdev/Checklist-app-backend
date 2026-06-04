import uuid
import tempfile
import subprocess
from types import SimpleNamespace
from datetime import datetime

from app.models.report import ReportStatus
from app.services import report as report_service
from app.services.pdf_generator import generate_report_pdf


def make_fake_report():
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
        report_status=ReportStatus.published,
        overall_score=78.4,
        max_possible_score=100,
        total_score_percentage=78.4,
        completion_percentage=91.2,
        total_questions=48,
        answered_questions=44,
        standard_covered_all=True,
        question_score_distribution=[],
        section_scores=[
            {"section_name": "Governance", "section_title": "Governance", "section_code": "GOV", "percentage": 82, "evidence_count": 5, "question_count": 12, "answered_question_count": 11},
            {"section_name": "Operations", "section_title": "Operations", "section_code": "OPS", "percentage": 68, "evidence_count": 3, "question_count": 10, "answered_question_count": 9},
            {"section_name": "Access Control", "section_title": "Access Control", "section_code": "ACC", "percentage": 74, "evidence_count": 7, "question_count": 15, "answered_question_count": 14},
            {"section_name": "Incident Response", "section_title": "Incident Response", "section_code": "INC", "percentage": 61, "evidence_count": 2, "question_count": 8, "answered_question_count": 7},
        ],
        chapter_data=[
            {"chapter_code": "CH-01", "title": "Chapter 1", "percentage": 75, "score": 7, "max_score": 10, "findings_count": 2},
            {"chapter_code": "CH-02", "title": "Chapter 2", "percentage": 64, "score": 6, "max_score": 10, "findings_count": 2},
        ],
        domain_data=[],
        findings=[
            {"priority": "high", "question_text": "Critical missing control", "recommendation": "Implement control X", "section_code": "GOV", "section_title": "Governance"},
            {"priority": "medium", "question_text": "Process gap in review cadence", "recommendation": "Add monthly review checkpoints", "section_code": "OPS", "section_title": "Operations"},
        ],
        section_summaries=[
            {"section_code": "GOV", "summary_text": "Governance framework is well established with clear policies and regular reviews."},
            {"section_code": "OPS", "summary_text": "Operational controls need improvement in documentation and monitoring."},
            {"section_code": "ACC", "summary_text": "Access control measures are partially implemented but lack regular review cycles."},
            {"section_code": "INC", "summary_text": "Incident response procedures exist but require testing and team training."},
        ],
        public_suggestions=[
            {"suggestion_text": "Do this next"},
            {"suggestion_text": "Add owner and timeline for remediation"},
        ],
        generated_at=datetime(2026, 5, 14),
        approved_at=datetime(2026, 5, 14),
        published_at=datetime(2026, 5, 14),
    )


def test_generate_report_pdf_end_to_end(monkeypatch, tmp_path):
    """End-to-end: render a PDF from the report generator using a fake report."""
    fake = make_fake_report()

    # Monkeypatch the service that fetches report data used by pdf_generator
    import app.services.pdf_generator as pdf_mod
    monkeypatch.setattr(pdf_mod, "get_customer_report_data", lambda db, report_id, company_id=None, lang_code="en": fake)

    # Call the API function (synchronous wrapper)
    pdf_bytes = generate_report_pdf(None, report_id=fake.report_id)
    assert pdf_bytes and len(pdf_bytes) > 0

    out_file = tmp_path / "report_sample.pdf"
    out_file.write_bytes(pdf_bytes)

    # Use pdfinfo to confirm page count
    result = subprocess.run(["pdfinfo", str(out_file)], capture_output=True, text=True)
    assert result.returncode == 0
    pages = 0
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            pages = int(line.split(':', 1)[1].strip())
    assert pages >= 1

    print(f"Generated PDF: {out_file} ({len(pdf_bytes)} bytes, {pages} pages)")
