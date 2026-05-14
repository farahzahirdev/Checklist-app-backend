#!/usr/bin/env python3
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import datetime

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / 'app' / 'templates'
OUT = Path('/tmp') / 'mock_report.html'

env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
template = env.get_template('customer_report.html')

now = datetime.utcnow()

sample = {
    'report_id': 'RPT-EXAMPLE-0001',
    'report_uuid': '00000000-0000-0000-0000-000000000001',
    'customer_name': 'Alice Example',
    'customer_email': 'alice@example.com',
    'company_name': 'Example Ltd',
    'company_website': 'example.com',
    'company_industry': 'Software',
    'company_size': '51-200',
    'company_region': 'EMEA',
    'company_country': 'Czech Republic',
    'company_description': 'Provider of example software',
    'checklist_title': 'Information Security Baseline',
    'assessment_date': now,
    'report_status': type('S', (), {'value': 'published'})(),
    'overall_score': 78.4,
    'max_possible_score': 100,
    'total_score_percentage': 78.4,
    'completion_percentage': 92.0,
    'total_questions': 120,
    'answered_questions': 110,
    'standard_covered_all': True,
    'question_score_distribution': [
        {'score': 4, 'count': 70, 'percentage': 58},
        {'score': 3, 'count': 25, 'percentage': 21},
        {'score': 2, 'count': 10, 'percentage': 8},
        {'score': 1, 'count': 15, 'percentage': 13},
    ],
    'section_scores': [
        {'section_name': 'Governance', 'percentage': 82},
        {'section_name': 'Asset Management', 'percentage': 76},
        {'section_name': 'Access Control', 'percentage': 68},
        {'section_name': 'Operations', 'percentage': 90},
    ],
    'chapter_data': [
        {'title': 'Chapter A', 'percentage': 82, 'score': 41, 'max_score': 50, 'findings_count': 2, 'chapter_code': 'A'},
        {'title': 'Chapter B', 'percentage': 76, 'score': 38, 'max_score': 50, 'findings_count': 4, 'chapter_code': 'B'},
    ],
    'domain_data': [],
    'findings': [
        {'priority': 'high', 'question_text': 'No incident response plan', 'recommendation': 'Create an incident response plan and test it.'},
        {'priority': 'medium', 'question_text': 'Missing asset inventory', 'recommendation': 'Maintain an up-to-date asset inventory.'},
    ],
    'section_summaries': [
        {'chapter_code': 'A', 'summary_text': 'Good governance practices, but need improvement in asset tagging.'},
        {'chapter_code': 'B', 'summary_text': 'Access control policies exist but not enforced.'},
    ],
    'public_suggestions': [
        {'suggestion_text': 'Start with a basic risk register.'},
        {'suggestion_text': 'Schedule security awareness training.'},
    ],
    'generated_at': now,
    'approved_at': now,
    'published_at': now,
}

html = template.render(**sample)
OUT.write_text(html, encoding='utf-8')
print('Wrote', OUT)
