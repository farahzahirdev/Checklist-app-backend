from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from app.utils.i18n_messages import translate
from sqlalchemy.orm import Session

from app.models.assessment import AnswerChoice, Assessment, AssessmentAnswer, AssessmentStatus, PriorityLevel
from app.models.checklist import ChecklistQuestion, ChecklistQuestionTranslation
from app.models.report import (
    Report,
    ReportEventType,
    ReportFinding,
    ReportReviewEvent,
    ReportSectionSummary,
    ReportStatus,
    ReportAdminSuggestion,
    ReportAdminNote,
)
from app.models.user import User
from app.schemas.report import (
    ReportFindingItem,
    ReportResponse,
    ReportSummaryItem,
    ReviewActionRequest,
    UpsertReportSummaryRequest,
    AdminSuggestionRequest,
    AdminNoteRequest,
    CustomerReportDataResponse,
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


def _question_content(db: Session, question_id: UUID) -> tuple[str, str | None]:
    translation = db.scalar(
        select(ChecklistQuestionTranslation)
        .where(ChecklistQuestionTranslation.question_id == question_id)
        .order_by(desc(ChecklistQuestionTranslation.created_at))
        .limit(1)
    )
    if translation is None:
        return "", None
    recommendation = translation.recommendation_template or translation.expected_implementation
    return translation.question_text, recommendation


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


def _get_report(db: Session, report_id: UUID, lang_code: str = "en") -> Report:
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("report_not_found", lang_code))
    return report


def _create_review_event(db: Session, *, report_id: UUID, actor_user_id: UUID, event_type: ReportEventType, note: str | None) -> None:
    db.add(ReportReviewEvent(report_id=report_id, actor_user_id=actor_user_id, event_type=event_type, event_note=note))


def generate_draft_report(db: Session, *, assessment_id: UUID, actor: User, lang_code: str = "en") -> ReportResponse:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("assessment_not_found", lang_code))
    if assessment.status != AssessmentStatus.submitted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("assessment_not_submitted", lang_code))

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
            finding_text, recommendation_text = _question_content(db, answer.question_id)
            db.add(
                ReportFinding(
                    report_id=report.id,
                    question_id=answer.question_id,
                    answer_id=answer.id,
                    priority=_priority_from_answer(answer),
                    finding_text=finding_text,
                    recommendation_text=recommendation_text,
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


def get_report_by_assessment(db: Session, *, assessment_id: UUID, lang_code: str = "en") -> ReportResponse:
    report = db.scalar(select(Report).where(Report.assessment_id == assessment_id))
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("report_not_found", lang_code))
    return _serialize_report(db, report)


def get_report(db: Session, *, report_id: UUID, lang_code: str = "en") -> ReportResponse:
    return _serialize_report(db, _get_report(db, report_id, lang_code))


def start_review(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest, lang_code: str = "en") -> ReportResponse:
    report = _get_report(db, report_id, lang_code)
    report.status = ReportStatus.under_review
    report.reviewed_by = actor.id
    report.reviewed_at = _now()
    _create_review_event(db, report_id=report.id, actor_user_id=actor.id, event_type=ReportEventType.review_started, note=payload.note)
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def request_changes(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest, lang_code: str = "en") -> ReportResponse:
    report = _get_report(db, report_id, lang_code)
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


def approve_report(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest, lang_code: str = "en") -> ReportResponse:
    report = _get_report(db, report_id, lang_code)
    report.status = ReportStatus.approved
    report.approved_by = actor.id
    report.approved_at = _now()
    _create_review_event(db, report_id=report.id, actor_user_id=actor.id, event_type=ReportEventType.approved, note=payload.note)
    db.commit()
    db.refresh(report)
    return _serialize_report(db, report)


def publish_report(db: Session, *, report_id: UUID, actor: User, final_pdf_storage_key: str, lang_code: str = "en") -> ReportResponse:
    report = _get_report(db, report_id, lang_code)
    if report.status != ReportStatus.approved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("report_not_approved", lang_code))

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
    lang_code: str = "en",
) -> ReportSummaryItem:
    report = _get_report(db, report_id, lang_code)
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


def list_report_summaries(db: Session, *, report_id: UUID, lang_code: str = "en") -> list[ReportSummaryItem]:
    _get_report(db, report_id, lang_code)
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


def list_report_findings(db: Session, *, report_id: UUID, lang_code: str = "en") -> list[ReportFindingItem]:
    _get_report(db, report_id, lang_code)
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


def add_admin_suggestion(db: Session, *, report_id: UUID, actor: User, payload: AdminSuggestionRequest, lang_code: str = "en") -> ReportAdminSuggestion:
    report = _get_report(db, report_id, lang_code)
    suggestion = ReportAdminSuggestion(
        report_id=report.id,
        admin_user_id=actor.id,
        suggestion_text=payload.suggestion_text,
        is_public=payload.is_public,
    )
    db.add(suggestion)
    
    _create_review_event(
        db,
        report_id=report.id,
        actor_user_id=actor.id,
        event_type=ReportEventType.summary_updated,
        note=f"Admin suggestion added: {'public' if payload.is_public else 'internal'}",
    )
    
    db.commit()
    db.refresh(suggestion)
    return suggestion


def add_admin_note(db: Session, *, report_id: UUID, actor: User, payload: AdminNoteRequest, lang_code: str = "en") -> ReportAdminNote:
    report = _get_report(db, report_id, lang_code)
    note = ReportAdminNote(
        report_id=report.id,
        admin_user_id=actor.id,
        note_text=payload.note_text,
        note_type=payload.note_type,
    )
    db.add(note)
    
    _create_review_event(
        db,
        report_id=report.id,
        actor_user_id=actor.id,
        event_type=ReportEventType.summary_updated,
        note=f"Admin note added: {payload.note_type}",
    )
    
    db.commit()
    db.refresh(note)
    return note


def list_admin_suggestions(db: Session, *, report_id: UUID, include_private: bool = False, actor: User | None = None, lang_code: str = "en") -> list[ReportAdminSuggestion]:
    report = _get_report(db, report_id, lang_code)
    query = select(ReportAdminSuggestion).where(ReportAdminSuggestion.report_id == report_id)
    
    # Only show public suggestions to non-admins
    if not include_private and (not actor or actor.role != UserRole.admin):
        query = query.where(ReportAdminSuggestion.is_public.is_(True))
    
    rows = db.scalars(query.order_by(desc(ReportAdminSuggestion.created_at))).all()
    return list(rows)


def list_admin_notes(db: Session, *, report_id: UUID, actor: User, lang_code: str = "en") -> list[ReportAdminNote]:
    # Only admins can see notes
    if actor.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    report = _get_report(db, report_id, lang_code)
    rows = db.scalars(
        select(ReportAdminNote).where(ReportAdminNote.report_id == report_id).order_by(desc(ReportAdminNote.created_at))
    ).all()
    return list(rows)


def get_customer_report_data(db: Session, *, report_id: UUID, lang_code: str = "en") -> CustomerReportDataResponse:
    """Get comprehensive report data for customer PDF generation"""
    report = _get_report(db, report_id, lang_code)
    
    # Only allow approved/published reports
    if report.status not in [ReportStatus.approved, ReportStatus.published]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Report not available")
    
    # Get assessment and user data
    assessment = db.get(Assessment, report.assessment_id)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    
    user = db.get(User, assessment.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Get checklist data
    from app.models.checklist import Checklist, ChecklistSection, ChecklistSectionTranslation
    checklist = db.get(Checklist, assessment.checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checklist not found")
    
    # Get checklist translation
    checklist_translation = _latest_checklist_translation(db, checklist.id)
    checklist_title = checklist_translation.title if checklist_translation else f"Checklist v{checklist.version}"
    
    # Calculate scores and gather data
    section_scores = _calculate_section_scores(db, assessment)
    chapter_data = _calculate_chapter_data(db, assessment)
    findings = _get_customer_findings(db, report_id)
    section_summaries = _get_section_summaries_for_customer(db, report_id)
    public_suggestions = _get_public_suggestions(db, report_id)
    
    # Calculate overall score
    overall_score = sum(s['score'] for s in section_scores)
    max_possible_score = sum(s['max_score'] for s in section_scores)
    completion_percentage = float(assessment.completion_percent)
    
    return CustomerReportDataResponse(
        report_id=report.id,
        assessment_id=assessment.id,
        customer_name=user.full_name or user.email,
        customer_email=user.email,
        checklist_title=checklist_title,
        assessment_date=assessment.submitted_at or assessment.created_at,
        report_status=report.status,
        overall_score=overall_score,
        max_possible_score=max_possible_score,
        completion_percentage=completion_percentage,
        section_scores=section_scores,
        chapter_data=chapter_data,
        findings=findings,
        section_summaries=section_summaries,
        public_suggestions=public_suggestions,
        generated_at=report.draft_generated_at or report.created_at,
        approved_at=report.approved_at,
        published_at=report.final_pdf_published_at,
    )


# Helper functions for customer report data
def _calculate_section_scores(db: Session, assessment: Assessment) -> list[dict]:
    """Calculate scores by section for radar chart"""
    from app.models.checklist import ChecklistSection, ChecklistSectionTranslation
    
    sections = db.scalars(
        select(ChecklistSection)
        .where(ChecklistSection.checklist_id == assessment.checklist_id)
        .order_by(ChecklistSection.display_order)
    ).all()
    
    section_scores = []
    for section in sections:
        # Get questions in this section
        from app.models.checklist import ChecklistQuestion
        questions = db.scalars(
            select(ChecklistQuestion)
            .where(
                ChecklistQuestion.section_id == section.id,
                ChecklistQuestion.is_active.is_(True)
            )
        ).all()
        
        if not questions:
            continue
            
        # Get answers for these questions
        question_ids = [q.id for q in questions]
        answers = db.scalars(
            select(AssessmentAnswer)
            .where(
                AssessmentAnswer.assessment_id == assessment.id,
                AssessmentAnswer.question_id.in_(question_ids)
            )
        ).all()
        
        answer_map = {a.question_id: a for a in answers}
        
        # Calculate section score
        total_score = 0
        max_score = 0
        
        for question in questions:
            max_score += 4  # Maximum score per question is 4 (Yes answer)
            answer = answer_map.get(question.id)
            if answer and answer.answer_score:
                total_score += answer.answer_score
        
        # Get section translation
        translation = _latest_section_translation(db, section.id)
        section_name = translation.title if translation else section.section_code
        
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        section_scores.append({
            "section_name": section_name,
            "section_id": section.id,
            "score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 1)
        })
    
    return section_scores


def _calculate_chapter_data(db: Session, assessment: Assessment) -> list[dict]:
    """Calculate chapter overview data"""
    from app.models.checklist import ChecklistQuestion
    
    # Group questions by report_chapter
    questions = db.scalars(
        select(ChecklistQuestion)
        .where(
            ChecklistQuestion.checklist_id == assessment.checklist_id,
            ChecklistQuestion.is_active.is_(True),
            ChecklistQuestion.report_chapter.is_not(None)
        )
    ).all()
    
    chapter_map = {}
    for question in questions:
        chapter = question.report_chapter or "Uncategorized"
        if chapter not in chapter_map:
            chapter_map[chapter] = {
                "chapter_code": chapter,
                "title": chapter,
                "questions": [],
                "score": 0,
                "max_score": 0
            }
        chapter_map[chapter]["questions"].append(question)
        chapter_map[chapter]["max_score"] += 4
    
    # Get answers and calculate scores
    question_ids = [q.id for q in questions]
    answers = db.scalars(
        select(AssessmentAnswer)
        .where(
            AssessmentAnswer.assessment_id == assessment.id,
            AssessmentAnswer.question_id.in_(question_ids)
        )
    ).all()
    
    answer_map = {a.question_id: a for a in answers}
    
    chapter_data = []
    for chapter_code, data in chapter_map.items():
        # Calculate score
        total_score = 0
        findings_count = 0
        
        for question in data["questions"]:
            answer = answer_map.get(question.id)
            if answer and answer.answer_score:
                total_score += answer.answer_score
                if answer.answer in [AnswerChoice.no, AnswerChoice.dont_know]:
                    findings_count += 1
        
        chapter_data.append({
            "chapter_code": chapter_code,
            "title": data["title"],
            "score": total_score,
            "max_score": data["max_score"],
            "percentage": round((total_score / data["max_score"] * 100), 1) if data["max_score"] > 0 else 0,
            "findings_count": findings_count,
            "recommendations": "See findings section for detailed recommendations"
        })
    
    return sorted(chapter_data, key=lambda x: x["chapter_code"])


def _get_customer_findings(db: Session, report_id: UUID) -> list[dict]:
    """Get findings for customer report"""
    findings = db.scalars(
        select(ReportFinding)
        .where(ReportFinding.report_id == report_id)
        .order_by(desc(ReportFinding.priority))
    ).all()
    
    customer_findings = []
    for finding in findings:
        customer_findings.append({
            "question_text": finding.finding_text,
            "answer": "No" if finding.priority == PriorityLevel.high else "Don't Know",
            "priority": finding.priority.value,
            "recommendation": finding.recommendation_text or "Review and improve this area"
        })
    
    return customer_findings


def _get_section_summaries_for_customer(db: Session, report_id: UUID) -> list[dict]:
    """Get admin-written section summaries for customer"""
    summaries = db.scalars(
        select(ReportSectionSummary)
        .where(ReportSectionSummary.report_id == report_id)
        .order_by(ReportSectionSummary.chapter_code)
    ).all()
    
    customer_summaries = []
    for summary in summaries:
        customer_summaries.append({
            "section_id": str(summary.section_id),
            "chapter_code": summary.chapter_code or "General",
            "summary_text": summary.summary_text
        })
    
    return customer_summaries


def _get_public_suggestions(db: Session, report_id: UUID) -> list[dict]:
    """Get public admin suggestions for customer"""
    suggestions = db.scalars(
        select(ReportAdminSuggestion)
        .where(
            ReportAdminSuggestion.report_id == report_id,
            ReportAdminSuggestion.is_public.is_(True)
        )
        .order_by(desc(ReportAdminSuggestion.created_at))
    ).all()
    
    customer_suggestions = []
    for suggestion in suggestions:
        customer_suggestions.append({
            "suggestion_text": suggestion.suggestion_text,
            "created_at": suggestion.created_at
        })
    
    return customer_suggestions
