"""
Background lifecycle tasks:
- expire_stale_assessments: Mark in-progress/not-started assessments past their expires_at as expired.
  This enforces the 7-day completion window — if a customer does not submit within 7 days their
  access is forfeited and they must repurchase.
- purge_assessment_evidence: Delete evidence files and clear note text for assessments whose
  retention window has elapsed (48 h after report published).  DB rows are kept; only S3 files
  and note_text are removed.
- purge_expired_reports: Delete report data (findings, summaries, PDF files) for reports whose
  access window has expired. Audit logs and payment records are preserved. Users can no longer
  access the checklist after this deletion.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy.orm import Session
from app.services.notifications import NotificationService, NotificationEventType, NotificationEvent

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Task: expire stale assessments
# ---------------------------------------------------------------------------

@shared_task(name="lifecycle.expire_stale_assessments", queue="celery")
def expire_stale_assessments() -> dict:
    """
    Mark assessments that have passed their expires_at timestamp as expired.
    Runs hourly. Enforces the 7-day no-submit forfeiture rule.
    """
    from app.db.session import SessionLocal
    from app.models.assessment import Assessment, AssessmentStatus
    from app.models.user import User

    db: Session = SessionLocal()
    expired_count = 0
    try:
        now = _now_utc()
        stale = (
            db.query(Assessment)
            .filter(
                Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
                Assessment.expires_at <= now,
            )
            .all()
        )
        for assessment in stale:
            assessment.status = AssessmentStatus.expired
            expired_count += 1
            
            # Send notification
            try:
                user = db.get(User, assessment.user_id)
                notify_lang = getattr(user, "preferred_language", "en") if user else "en"
                event = NotificationEvent(
                    event_type=NotificationEventType.ASSESSMENT_EXPIRED,
                    user_id=assessment.user_id,
                    assessment_id=assessment.id,
                    lang_code=notify_lang or "en",
                )
                notification_service = NotificationService(db)
                notification_service.notify(event)
            except Exception as e:
                logger.error(f"Failed to send assessment_expired notification for {assessment.id}: {e}", exc_info=True)
        
        if expired_count:
            db.commit()
            logger.info("Expired %d stale assessments", expired_count)
    except Exception:
        db.rollback()
        logger.exception("Error expiring stale assessments")
        raise
    finally:
        db.close()

    return {"expired": expired_count}


# ---------------------------------------------------------------------------
# Task: purge evidence after retention period
# ---------------------------------------------------------------------------

@shared_task(name="lifecycle.purge_assessment_evidence", queue="celery")
def purge_assessment_evidence() -> dict:
    """
    For assessments whose retention_expires_at has passed (48 h after report
    published) and that have not yet been purged:
    - Delete evidence files from S3
    - Set Media.is_active = False and Media.file_path = '' (keeps the row)
    - Set AssessmentEvidenceFile.purged_at = now
    - Clear AssessmentAnswer.note_text
    - Set AssessmentAnswer.purged_at = now
    - Set Assessment.purged_at = now
    """
    from app.db.session import SessionLocal
    from app.models.assessment import Assessment, AssessmentAnswer, AssessmentEvidenceFile, AssessmentStatus
    from app.models.media import Media
    from app.utils.s3_upload import delete_s3_object

    db: Session = SessionLocal()
    purged_assessments = 0
    purged_files = 0
    try:
        now = _now_utc()
        due = (
            db.query(Assessment)
            .filter(
                Assessment.retention_expires_at <= now,
                Assessment.purged_at.is_(None),
            )
            .all()
        )

        for assessment in due:
            # Purge evidence files for this assessment
            evidence_files = (
                db.query(AssessmentEvidenceFile)
                .filter(
                    AssessmentEvidenceFile.assessment_id == assessment.id,
                    AssessmentEvidenceFile.purged_at.is_(None),
                )
                .all()
            )
            for ef in evidence_files:
                media: Media | None = db.get(Media, ef.media_id)
                if media and media.file_path:
                    deleted = delete_s3_object(media.file_path)
                    if deleted:
                        purged_files += 1
                    # Deactivate media record regardless (file may already be gone)
                    media.is_active = False
                    media.file_path = ""
                ef.purged_at = now

            # Clear note_text from answers
            (
                db.query(AssessmentAnswer)
                .filter(
                    AssessmentAnswer.assessment_id == assessment.id,
                    AssessmentAnswer.purged_at.is_(None),
                )
                .update(
                    {
                        AssessmentAnswer.note_text: None,
                        AssessmentAnswer.purged_at: now,
                    },
                    synchronize_session=False,
                )
            )

            assessment.purged_at = now
            purged_assessments += 1

        if purged_assessments:
            db.commit()
            logger.info(
                "Purged evidence for %d assessments (%d files removed from S3)",
                purged_assessments,
                purged_files,
            )
    except Exception:
        db.rollback()
        logger.exception("Error purging assessment evidence")
        raise
    finally:
        db.close()

    return {"purged_assessments": purged_assessments, "purged_files": purged_files}


# ---------------------------------------------------------------------------
# Task: purge expired reports
# ---------------------------------------------------------------------------

@shared_task(name="lifecycle.purge_expired_reports", queue="celery")
def purge_expired_reports() -> dict:
    """
    Delete report data for reports whose access window has expired.
    - Delete report findings, section summaries, and review events
    - Delete PDF files from S3 and clear storage keys
    - Mark report as deleted with timestamp
    - Preserve audit logs and payment records
    - Users can no longer access the checklist after deletion
    """
    from app.db.session import SessionLocal
    from app.models.report import Report, ReportFinding, ReportSectionSummary, ReportReviewEvent
    from app.models.assessment import Assessment
    from app.models.access_window import AccessWindow
    from app.utils.s3_upload import delete_s3_object
    from app.services.audit_log import create_audit_log, AuditAction

    db: Session = SessionLocal()
    purged_reports = 0
    purged_findings = 0
    purged_summaries = 0
    purged_events = 0
    purged_pdfs = 0

    try:
        now = _now_utc()

        # Find reports where the associated assessment's access window has expired
        # and the report has not yet been deleted
        expired_reports_query = (
            db.query(Report, Assessment, AccessWindow)
            .join(Assessment, Report.assessment_id == Assessment.id)
            .outerjoin(AccessWindow, Assessment.access_window_id == AccessWindow.id)
            .filter(
                Report.final_deleted_at.is_(None),
                Assessment.expires_at <= now,
            )
            .all()
        )

        for report, assessment, access_window in expired_reports_query:
            # Delete report findings
            findings_count = db.query(ReportFinding).filter(
                ReportFinding.report_id == report.id
            ).count()
            if findings_count > 0:
                db.query(ReportFinding).filter(
                    ReportFinding.report_id == report.id
                ).delete(synchronize_session=False)
                purged_findings += findings_count

            # Delete report section summaries
            summaries_count = db.query(ReportSectionSummary).filter(
                ReportSectionSummary.report_id == report.id
            ).count()
            if summaries_count > 0:
                db.query(ReportSectionSummary).filter(
                    ReportSectionSummary.report_id == report.id
                ).delete(synchronize_session=False)
                purged_summaries += summaries_count

            # Delete report review events
            events_count = db.query(ReportReviewEvent).filter(
                ReportReviewEvent.report_id == report.id
            ).count()
            if events_count > 0:
                db.query(ReportReviewEvent).filter(
                    ReportReviewEvent.report_id == report.id
                ).delete(synchronize_session=False)
                purged_events += events_count

            # Delete PDF file from S3 if exists
            if report.final_pdf_storage_key:
                deleted = delete_s3_object(report.final_pdf_storage_key)
                if deleted:
                    purged_pdfs += 1
                report.final_pdf_storage_key = None
                report.final_pdf_password_encrypted = None

            # Mark report as deleted
            report.final_deleted_at = now
            report.management_summary = None  # Clear sensitive data
            report.draft_deleted_at = now  # Also mark draft as deleted

            # Create audit log for report deletion
            try:
                create_audit_log(
                    db=db,
                    action=AuditAction.report_delete,
                    target_entity="report",
                    target_id=report.id,
                    target_user_id=assessment.user_id,
                    changes_summary=f"Report data purged after access window expiry. Assessment: {assessment.id}, Access Window: {access_window.id if access_window else None}",
                    success=True,
                )
            except Exception as e:
                logger.error(f"Failed to create audit log for report deletion {report.id}: {e}", exc_info=True)

            purged_reports += 1

        if purged_reports:
            db.commit()
            logger.info(
                "Purged data for %d expired reports (%d findings, %d summaries, %d events, %d PDFs)",
                purged_reports,
                purged_findings,
                purged_summaries,
                purged_events,
                purged_pdfs,
            )
    except Exception:
        db.rollback()
        logger.exception("Error purging expired reports")
        raise
    finally:
        db.close()

    return {
        "purged_reports": purged_reports,
        "purged_findings": purged_findings,
        "purged_summaries": purged_summaries,
        "purged_events": purged_events,
        "purged_pdfs": purged_pdfs,
    }
