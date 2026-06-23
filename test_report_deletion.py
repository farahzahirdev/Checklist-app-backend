#!/usr/bin/env python3
"""
Test script for report deletion mechanism.
This script tests the report deletion logic after access window expiry.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.report import Report
from app.models.assessment import Assessment
from app.models.access_window import AccessWindow


def test_report_deletion():
    """Test the report deletion mechanism."""
    
    with SessionLocal() as db:
        # Find reports with expired access windows
        now = datetime.now(timezone.utc)
        
        # Check for reports that should be deleted
        expired_reports = (
            db.query(Report, Assessment, AccessWindow)
            .join(Assessment, Report.assessment_id == Assessment.id)
            .outerjoin(AccessWindow, Assessment.access_window_id == AccessWindow.id)
            .filter(
                Report.final_deleted_at.is_(None),
                Assessment.expires_at <= now,
            )
            .all()
        )
        
        print(f"Found {len(expired_reports)} reports with expired access windows that should be deleted")
        
        for report, assessment, access_window in expired_reports:
            print(f"\nReport ID: {report.id}")
            print(f"Assessment ID: {assessment.id}")
            print(f"Assessment expires_at: {assessment.expires_at}")
            print(f"Access Window ID: {access_window.id if access_window else 'None'}")
            print(f"Access Window expires_at: {access_window.expires_at if access_window else 'None'}")
            print(f"Report status: {report.status}")
            print(f"Report final_deleted_at: {report.final_deleted_at}")
            
            # Check if the report would be accessible
            try:
                from app.services.report import get_customer_report_data
                from app.core.config import get_settings
                
                # This should fail for deleted reports
                settings = get_settings()
                test_lang = "en"
                
                try:
                    report_data = get_customer_report_data(
                        db, 
                        report_id=report.id, 
                        lang_code=test_lang
                    )
                    print("WARNING: Report data is still accessible (should not be after deletion)")
                except Exception as e:
                    print(f"Expected: Report access blocked with error: {e}")
                    
            except ImportError as e:
                print(f"Could not import report service: {e}")
        
        # Check for reports that have already been deleted
        deleted_reports = (
            db.query(Report)
            .filter(Report.final_deleted_at.isnot(None))
            .all()
        )
        
        print(f"\n\nFound {len(deleted_reports)} reports that have already been deleted")
        for report in deleted_reports:
            print(f"Report ID: {report.id} - Deleted at: {report.final_deleted_at}")
        
        # Check if deleted reports can still be accessed
        for report in deleted_reports[:3]:  # Check first 3 deleted reports
            try:
                from app.services.report import get_customer_report_data
                try:
                    report_data = get_customer_report_data(
                        db, 
                        report_id=report.id, 
                        lang_code="en"
                    )
                    print(f"WARNING: Deleted report {report.id} is still accessible!")
                except Exception as e:
                    print(f"Good: Deleted report {report.id} access blocked: {e}")
            except ImportError:
                pass


if __name__ == "__main__":
    print("Testing Report Deletion Mechanism")
    print("=" * 50)
    test_report_deletion()
    print("\nTest completed.")