"""
Background lifecycle tasks:
- expire_stale_assessments: Mark in-progress/not-started assessments past their expires_at as expired.
  This enforces the 7-day completion window — if a customer does not submit within 7 days their
  access is forfeited and they must repurchase.
- purge_assessment_evidence: Delete evidence files and clear note text for assessments whose
  retention window has elapsed (48 h after report published).  DB rows are kept; only S3 files
  and note_text are removed.
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
                event = NotificationEvent(
                    event_type=NotificationEventType.ASSESSMENT_EXPIRED,
                    user_id=assessment.user_id,
                    assessment_id=assessment.id,
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
