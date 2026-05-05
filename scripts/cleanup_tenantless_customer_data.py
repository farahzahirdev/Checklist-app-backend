#!/usr/bin/env python3

"""Remove legacy customer data that is not linked to a company.

This deletes only rows where company_id IS NULL from the tenant-scoped tables.
Dependent rows are removed by database cascades where configured.
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.access_window import AccessWindow
from app.models.assessment import Assessment
from app.models.payment import Payment
from app.models.report import Report


def _count(session, model, *, where_clause) -> int:
    return session.scalar(select(func.count()).select_from(model).where(where_clause)) or 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually delete rows instead of only showing counts")
    args = parser.parse_args()

    with SessionLocal() as session:
        targets = [
            ("reports", Report, Report.company_id.is_(None)),
            ("assessments", Assessment, Assessment.company_id.is_(None)),
            ("payments", Payment, Payment.company_id.is_(None)),
            ("access_windows", AccessWindow, AccessWindow.company_id.is_(None)),
        ]

        print("Tenantless row counts before cleanup:")
        for label, model, where_clause in targets:
            print(f"- {label}: {_count(session, model, where_clause=where_clause)}")

        if not args.execute:
            print("Dry run only. Re-run with --execute to delete these rows.")
            return 0

        try:
            deleted_reports = session.query(Report).filter(Report.company_id.is_(None)).delete(synchronize_session=False)
            deleted_payments = session.query(Payment).filter(Payment.company_id.is_(None)).delete(synchronize_session=False)
            deleted_assessments = session.query(Assessment).filter(Assessment.company_id.is_(None)).delete(synchronize_session=False)
            deleted_access_windows = session.query(AccessWindow).filter(AccessWindow.company_id.is_(None)).delete(synchronize_session=False)

            session.commit()
        except Exception:
            session.rollback()
            raise

        print("Deleted rows:")
        print(f"- reports: {deleted_reports}")
        print(f"- payments: {deleted_payments}")
        print(f"- assessments: {deleted_assessments}")
        print(f"- access_windows: {deleted_access_windows}")

        print("Tenantless row counts after cleanup:")
        for label, model, where_clause in targets:
            print(f"- {label}: {_count(session, model, where_clause=where_clause)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())