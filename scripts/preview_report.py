#!/usr/bin/env python3
import sys
import traceback
from pathlib import Path

from app.db.session import SessionLocal
from sqlalchemy import select
from app.models.report import Report, ReportStatus

from app.services.pdf_generator import generate_report_html_preview

OUT = Path('/tmp')


def main():
    db = SessionLocal()
    try:
        rpt = db.scalar(
            select(Report).where(Report.status.in_([ReportStatus.published, ReportStatus.approved])).limit(1)
        )
        if not rpt:
            print('No approved/published report found in DB. Exiting.')
            return 2
        print(f'Found report: {rpt.id} status={rpt.status}')
        try:
            html = generate_report_html_preview(db, report_id=rpt.id, company_id=rpt.company_id)
        except Exception as e:
            print('Error rendering preview:')
            traceback.print_exc()
            return 3
        out_file = OUT / f'report_preview_{rpt.id}.html'
        out_file.write_text(html, encoding='utf-8')
        print(f'Wrote preview to {out_file}')
        return 0
    finally:
        db.close()


if __name__ == '__main__':
    sys.exit(main())
