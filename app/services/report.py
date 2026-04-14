from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.assessment import AnswerChoice, Assessment, AssessmentAnswer, AssessmentStatus, PriorityLevel
from app.models.checklist import ChecklistQuestion
from app.models.report import (
    Report,
    ReportEventType,
    ReportFinding,
    ReportReviewEvent,
    ReportSectionSummary,
    ReportStatus,
)
from app.models.user import User
from app.schemas.report import (
    ReportFindingItem,
    ReportResponse,
    ReportSummaryItem,
    ReviewActionRequest,
    UpsertReportSummaryRequest,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _priority_from_answer(answer: AssessmentAnswer) -> PriorityLevel:
    if answer.weighted_priority is not None:
        return answer.weighted_priority
    if answer.answer == AnswerChoice.no:
        return PriorityLevel.high
    if answer.answer == AnswerChoice.dont_know:
        return PriorityLevel.medium
    return PriorityLevel.low


def _report_counts(db: Session, report_id: UUID) -> tuple[int, int]:
    findings = db.scalar(select(func.count(ReportFinding.id)).where(ReportFinding.report_id == report_id)) or 0
    summaries = db.scalar(select(func.count(ReportSectionSummary.id)).where(ReportSectionSummary.report_id == report_id)) or 0
    return findings, summaries


def _serialize_report(db: Session, report: Report) -> ReportResponse:
    findings_count, summaries_count = _report_counts(db, report.id)
    return ReportResponse(
        id=report.id,
        assessment_id=report.assessment_id,
        status=report.status,
        draft_generated_at=report.draft_generated_at,
        reviewed_by=report.reviewed_by,
        reviewed_at=report.reviewed_at,
        approved_by=report.approved_by,
        approved_at=report.approved_at,
        final_pdf_storage_key=report.final_pdf_storage_key,
        final_pdf_published_at=report.final_pdf_published_at,
        findings_count=findings_count,
        summaries_count=summaries_count,
    )


def _get_report(db: Session, report_id: UUID) -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")
    return report


def _create_review_event(db: Session, *, report_id: UUID, actor_user_id: UUID, event_type: ReportEventType, note: str | None) -> None:
    db.add(ReportReviewEvent(report_id=report_id, actor_user_id=actor_user_id, event_type=event_type, event_note=note))


def generate_draft_report(db: Session, *, assessment_id: UUID, actor: User) -> ReportResponse:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="assessment_not_found")
    if assessment.status != AssessmentStatus.submitted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="assessment_not_submitted")

    existing = db.scalar(select(Report).where(Report.assessment_id == assessment_id))
    if existing is not None:
        return _serialize_report(db, existing)

    now = _now()
    report = Report(assessment_id=assessment_id, status=ReportStatus.draft_generated, draft_generated_at=now)
    db.add(report)
    db.flush()

    answers = db.scalars(select(AssessmentAnswer).where(AssessmentAnswer.assessment_id == assessment_id)).all()
    for answer in answers:
        if answer.answer in {AnswerChoice.no, AnswerChoice.dont_know}:
            question = db.get(ChecklistQuestion, answer.question_id)
            if question is None:
                continue
            db.add(
                ReportFinding(
                    report_id=report.id,
                    question_id=answer.question_id,
                    answer_id=answer.id,
                    priority=_priority_from_answer(answer),
                    finding_text=question.legal_requirement,
                    recommendation_text=question.recommendation_template or question.expected_implementation,
                )
            )

    _create_review_event(
        db,
        report_id=report.id,
        actor_user_id=actor.id,
        event_type=ReportEventType.draft_generated,
        note="Draft generated from submitted assessment",
    )

    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def get_report_by_assessment(db: Session, *, assessment_id: UUID) -> ReportResponse:
    report = db.scalar(select(Report).where(Report.assessment_id == assessment_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report_not_found")
    return _serialize_report(db, report)


def get_report(db: Session, *, report_id: UUID) -> ReportResponse:
    return _serialize_report(db, _get_report(db, report_id))


def start_review(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest) -> ReportResponse:
    report = _get_report(db, report_id)
    report.status = ReportStatus.under_review
    report.reviewed_by = actor.id
    report.reviewed_at = _now()
    _create_review_event(db, report_id=report.id, actor_user_id=actor.id, event_type=ReportEventType.review_started, note=payload.note)
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def request_changes(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest) -> ReportResponse:
    report = _get_report(db, report_id)
    report.status = ReportStatus.changes_requested
    _create_review_event(
        db,
        report_id=report.id,
        actor_user_id=actor.id,
        event_type=ReportEventType.changes_requested,
        note=payload.note,
    )
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def approve_report(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest) -> ReportResponse:
    report = _get_report(db, report_id)
    report.status = ReportStatus.approved
    report.approved_by = actor.id
    report.approved_at = _now()
    _create_review_event(db, report_id=report.id, actor_user_id=actor.id, event_type=ReportEventType.approved, note=payload.note)
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def publish_report(db: Session, *, report_id: UUID, actor: User, final_pdf_storage_key: str) -> ReportResponse:
    report = _get_report(db, report_id)
    if report.status != ReportStatus.approved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="report_not_approved")

    report.status = ReportStatus.published
    report.final_pdf_storage_key = final_pdf_storage_key
    report.final_pdf_published_at = _now()
    _create_review_event(
        db,
        report_id=report.id,
        actor_user_id=actor.id,
        event_type=ReportEventType.published,
        note="Final PDF published",
    )
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def upsert_report_summary(
    db: Session,
    *,
    report_id: UUID,
    actor: User,
    payload: UpsertReportSummaryRequest,
) -> ReportSummaryItem:
    report = _get_report(db, report_id)
    summary = db.scalar(
        select(ReportSectionSummary).where(
            ReportSectionSummary.report_id == report_id,
            ReportSectionSummary.section_id == payload.section_id,
            ReportSectionSummary.chapter_code == payload.chapter_code,
        )
    )
    if summary is None:
        summary = ReportSectionSummary(
            report_id=report.id,
            section_id=payload.section_id,
            chapter_code=payload.chapter_code,
            summary_text=payload.summary_text,
            created_by=actor.id,
            updated_by=actor.id,
        )
        db.add(summary)
    else:
        summary.summary_text = payload.summary_text
        summary.updated_by = actor.id

    _create_review_event(
        db,
        report_id=report.id,
        actor_user_id=actor.id,
        event_type=ReportEventType.summary_updated,
        note="Section summary updated",
    )
    db.commit()
    db.refresh(summary)

    return ReportSummaryItem(
        id=summary.id,
        section_id=summary.section_id,
        chapter_code=summary.chapter_code,
        summary_text=summary.summary_text,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def list_report_summaries(db: Session, *, report_id: UUID) -> list[ReportSummaryItem]:
    _get_report(db, report_id)
    rows = db.scalars(select(ReportSectionSummary).where(ReportSectionSummary.report_id == report_id).order_by(desc(ReportSectionSummary.updated_at))).all()
    return [
        ReportSummaryItem(
            id=row.id,
            section_id=row.section_id,
            chapter_code=row.chapter_code,
            summary_text=row.summary_text,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


def list_report_findings(db: Session, *, report_id: UUID) -> list[ReportFindingItem]:
    _get_report(db, report_id)
    rows = db.scalars(select(ReportFinding).where(ReportFinding.report_id == report_id).order_by(desc(ReportFinding.created_at))).all()
    return [
        ReportFindingItem(
            id=row.id,
            question_id=row.question_id,
            answer_id=row.answer_id,
            priority=row.priority,
            finding_text=row.finding_text,
            recommendation_text=row.recommendation_text,
            created_at=row.created_at,
        )
        for row in rows
    ]
