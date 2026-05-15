#!/usr/bin/env python3

"""Remove legacy customer data that is not linked to a company.

This deletes only rows where company_id IS NULL from the tenant-scoped tables.
Payment history is retained so customer billing records remain visible after access expires.
Dependent rows are removed by database cascades where configured.
"""

from __future__ import annotations

import argparse

from sqlalchemy import text

from app.db.session import SessionLocal


def _count(session, table_name: str) -> int:
    res = session.execute(text(f"SELECT count(*) FROM {table_name} WHERE company_id IS NULL"))
    return int(res.scalar() or 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Actually delete rows instead of only showing counts")
    args = parser.parse_args()

    with SessionLocal() as session:
        targets = ["reports", "assessments", "payments", "access_windows"]

        print("Tenantless row counts before cleanup:")
        for table in targets:
            print(f"- {table}: {_count(session, table)}")

        if not args.execute:
            print("Dry run only. Re-run with --execute to delete these rows.")
            return 0

        try:
            deleted_reports = session.execute(text("DELETE FROM reports WHERE company_id IS NULL RETURNING id"))
            deleted_reports_count = len(deleted_reports.fetchall())

            deleted_assessments = session.execute(text("DELETE FROM assessments WHERE company_id IS NULL RETURNING id"))
            deleted_assessments_count = len(deleted_assessments.fetchall())

            deleted_access_windows = session.execute(text("DELETE FROM access_windows WHERE company_id IS NULL RETURNING id"))
            deleted_access_windows_count = len(deleted_access_windows.fetchall())

            session.commit()
        except Exception:
            session.rollback()
            raise

        print("Deleted rows:")
        print(f"- reports: {deleted_reports_count}")
        print("- payments: retained")
        print(f"- assessments: {deleted_assessments_count}")
        print(f"- access_windows: {deleted_access_windows_count}")

        print("Tenantless row counts after cleanup:")
        for table in targets:
            print(f"- {table}: {_count(session, table)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())