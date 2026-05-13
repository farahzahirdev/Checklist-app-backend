from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from app.services.admin_checklist import _latest_section_translation
from app.services.assessment import _latest_checklist_translation
from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import selectinload
from app.utils.i18n_messages import translate
from sqlalchemy.orm import Session

from app.models.assessment import AnswerChoice, Assessment, AssessmentAnswer, AssessmentStatus, PriorityLevel
from app.models.assessment_review import AssessmentReview, AnswerReview, SuggestionType
from app.models.checklist import ChecklistQuestion, ChecklistQuestionTranslation
from app.models.report import (
    Report,
    ReportEventType,
    ReportFinding,
    ReportReviewEvent,
    ReportSectionSummary,
    ReportStatus,
)
from app.models.company import Company
from app.models.user import User
from app.services.audit_log import create_audit_log
from app.schemas.report import (
    ReportFindingItem,
    ReportResponse,
    ReportSummaryItem,
    ReviewActionRequest,
    UpsertReportSummaryRequest,
    CustomerReportDataResponse,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _priority_from_answer(answer: AssessmentAnswer) -> PriorityLevel:
    if answer.weighted_priority is not None:
        return answer.weighted_priority
    if answer.answer == AnswerChoice.one:
        return PriorityLevel.high
    if answer.answer == AnswerChoice.two:
        return PriorityLevel.medium
    return PriorityLevel.low


def _report_counts(db: Session, report_id: UUID) -> tuple[int, int]:
    findings = db.scalar(select(func.count(ReportFinding.id)).where(ReportFinding.report_id == report_id)) or 0
    summaries = db.scalar(select(func.count(ReportSectionSummary.id)).where(ReportSectionSummary.report_id == report_id)) or 0
    return findings, summaries


def _company_identifier(company: Company | None) -> str:
    if company is None:
        return "UNKNOWN"

    candidates: list[str] = []
    if company.website:
        parsed = urlparse(company.website if "//" in company.website else f"https://{company.website}")
        host = parsed.netloc or parsed.path
        if host:
            candidates.append(host.split(":")[0])
    if company.slug:
        candidates.append(company.slug)
    if company.name:
        candidates.append(company.name)

    for candidate in candidates:
        token = re.sub(r"[^A-Za-z0-9]+", "", candidate.split(".")[0]).upper()
        if token:
            return token[:24]

    return "UNKNOWN"


def _report_code(report: Report, company: Company | None) -> str:
    reference_time = report.draft_generated_at or report.created_at or _now()
    return f"CKB-{reference_time:%Y}-%m%d-{_company_identifier(company)}-{reference_time:%H%M%S}"


def _report_company(report: Report, db: Session) -> Company | None:
    if report.company is not None:
        return report.company

    if report.company_id is not None:
        return db.get(Company, report.company_id)

    assessment = db.get(Assessment, report.assessment_id)
    if assessment is not None and assessment.company_id is not None:
        return db.get(Company, assessment.company_id)

    return None


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
    company = _report_company(report, db)
    return ReportResponse(
        id=report.id,
        assessment_id=report.assessment_id,
        report_code=report.report_code or _report_code(report, company),
        company_id=report.company_id,
        company_name=company.name if company else None,
        company_website=company.website if company else None,
        company_industry=company.industry if company else None,
        company_size=company.size if company else None,
        company_region=company.region if company else None,
        company_country=company.country if company else None,
        company_description=company.description if company else None,
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


def _log_report_audit(
    db: Session,
    *,
    action: str,
    report: Report,
    actor_user_id: UUID,
    changes_summary: str,
    after_data: dict | None = None,
) -> None:
    try:
        assessment = db.get(Assessment, report.assessment_id)
        create_audit_log(
            db=db,
            action=action,
            target_entity="report",
            target_id=report.id,
            actor_user_id=actor_user_id,
            target_user_id=assessment.user_id if assessment else None,
            after_json=after_data,
            changes_summary=changes_summary,
        )
    except Exception as e:
        print(f"Error creating audit log for report {report.id}: {e}")


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
    report = Report(
        report_code=None,
        assessment_id=assessment_id,
        company_id=assessment.company_id,
        status=ReportStatus.draft_generated,
        draft_generated_at=now,
    )
    db.add(report)
    db.flush()
    draft_company = db.get(Company, assessment.company_id) if assessment.company_id is not None else None
    report.report_code = _report_code(report, draft_company)

    answers = db.scalars(select(AssessmentAnswer).where(AssessmentAnswer.assessment_id == assessment_id)).all()
    for answer in answers:
        if answer.answer in {AnswerChoice.one, AnswerChoice.two}:
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

    _log_report_audit(
        db,
        action="report_create",
        report=report,
        actor_user_id=actor.id,
        changes_summary=f"Generated draft report for assessment {assessment_id}",
        after_data={"assessment_id": str(assessment_id), "status": str(report.status)},
    )

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

    _log_report_audit(
        db,
        action="report_update",
        report=report,
        actor_user_id=actor.id,
        changes_summary=f"Started review for report {report_id}",
        after_data={"status": str(report.status), "note": payload.note},
    )

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

    _log_report_audit(
        db,
        action="report_changes_request",
        report=report,
        actor_user_id=actor.id,
        changes_summary=f"Requested changes for report {report_id}",
        after_data={"status": str(report.status), "note": payload.note},
    )

    return _serialize_report(db, report)


def approve_report(db: Session, *, report_id: UUID, actor: User, payload: ReviewActionRequest, lang_code: str = "en") -> ReportResponse:
    report = _get_report(db, report_id, lang_code)
    report.status = ReportStatus.approved
    report.approved_by = actor.id
    report.approved_at = _now()
    _create_review_event(db, report_id=report.id, actor_user_id=actor.id, event_type=ReportEventType.approved, note=payload.note)
    db.commit()
    db.refresh(report)

    _log_report_audit(
        db,
        action="report_approve",
        report=report,
        actor_user_id=actor.id,
        changes_summary=f"Approved report {report_id}",
        after_data={"status": str(report.status), "note": payload.note},
    )

    return _serialize_report(db, report)


def list_reports(db: Session, *, status: str | None = None, skip: int = 0, limit: int = 50, lang_code: str = "en") -> dict[str, Any]:
    """List all reports with optional status filtering."""
    from sqlalchemy.orm import joinedload
    from app.models.checklist import Checklist, ChecklistTranslation
    
    query = (
        db.query(Report)
        .options(
            joinedload(Report.assessment).joinedload(Assessment.user),
            joinedload(Report.assessment).joinedload(Assessment.checklist).joinedload(Checklist.translations),
            joinedload(Report.company),
        )
        .order_by(desc(Report.created_at))
    )
    
    if status:
        try:
            status_enum = ReportStatus(status)
            query = query.filter(Report.status == status_enum)
        except ValueError:
            pass  # Invalid status, ignore filter
    
    total = db.scalar(select(func.count(Report.id)))
    reports = query.offset(skip).limit(limit).all()
    
    # Batch query findings and summaries counts to avoid N+1 queries
    counts_data = db.execute(
        select(
            ReportFinding.report_id,
            func.count(ReportFinding.id).label('findings_count')
        )
        .group_by(ReportFinding.report_id)
    ).all()
    findings_counts = {row.report_id: row.findings_count for row in counts_data}
    
    summaries_data = db.execute(
        select(
            ReportSectionSummary.report_id,
            func.count(ReportSectionSummary.id).label('summaries_count')
        )
        .group_by(ReportSectionSummary.report_id)
    ).all()
    summaries_counts = {row.report_id: row.summaries_count for row in summaries_data}
    
    # Cache reviewer lookups
    reviewer_cache = {}
    
    report_items = []
    for report in reports:
        # Get reviewer name (with caching)
        reviewer_name = None
        if report.reviewed_by:
            if report.reviewed_by not in reviewer_cache:
                reviewer = db.get(User, report.reviewed_by)
                reviewer_cache[report.reviewed_by] = reviewer.email if reviewer else None
            reviewer_name = reviewer_cache[report.reviewed_by]
        
        # Get checklist title from translation
        checklist_title = None
        if report.assessment.checklist and report.assessment.checklist.translations:
            # Get the first translation (English if available)
            translation = report.assessment.checklist.translations[0]
            checklist_title = translation.title
        
        report_items.append({
            "id": str(report.id),
            "assessment_id": str(report.assessment_id),
            "report_code": report.report_code or _report_code(report, report.company),
            "company_id": str(report.company_id) if report.company_id else None,
            "company_name": report.company.name if report.company else None,
            "company_website": report.company.website if report.company else None,
            "company_industry": report.company.industry if report.company else None,
            "company_size": report.company.size if report.company else None,
            "company_region": report.company.region if report.company else None,
            "company_country": report.company.country if report.company else None,
            "customer_email": report.assessment.user.email if report.assessment.user else None,
            "customer_name": report.assessment.user.email if report.assessment.user else None,
            "checklist_title": checklist_title,
            "checklist_version": report.assessment.checklist.version if report.assessment.checklist else None,
            "status": report.status,
            "draft_generated_at": report.draft_generated_at.isoformat() if report.draft_generated_at else None,
            "reviewed_at": report.reviewed_at.isoformat() if report.reviewed_at else None,
            "approved_at": report.approved_at.isoformat() if report.approved_at else None,
            "findings_count": findings_counts.get(report.id, 0),
            "summaries_count": summaries_counts.get(report.id, 0),
            "reviewer_name": reviewer_name,
        })
    
    return {
        "reports": report_items,
        "total": total,
    }


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

    _log_report_audit(
        db,
        action="report_publish",
        report=report,
        actor_user_id=actor.id,
        changes_summary=f"Published report {report_id}",
        after_data={"status": str(report.status), "final_pdf_storage_key": final_pdf_storage_key},
    )

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

    _log_report_audit(
        db,
        action="report_update",
        report=report,
        actor_user_id=actor.id,
        changes_summary=f"Updated report summary for section {payload.section_id}",
        after_data={"section_id": str(payload.section_id), "chapter_code": payload.chapter_code},
    )

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










def get_customer_report_data(db: Session, *, report_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> CustomerReportDataResponse:
    """Get comprehensive report data for customer PDF generation"""
    report = _get_report(db, report_id, lang_code)
    if company_id is not None and report.company_id is not None and report.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("report_not_found", lang_code))
    
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

    company = report.company or (db.get(Company, report.company_id) if report.company_id else None)
    if company is None and assessment.company_id is not None:
        company = db.get(Company, assessment.company_id)
    
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
    domain_data = _calculate_domain_data(db, assessment)
    question_score_distribution, total_questions, answered_questions = _calculate_question_distribution(db, assessment)
    chapter_data = _calculate_chapter_data(db, assessment)
    findings = _get_customer_findings(db, report_id)
    section_summaries = _get_section_summaries_for_customer(db, report_id)
    public_suggestions = _get_public_suggestions(db, report_id)
    
    # Calculate overall score
    overall_score = sum(s['score'] for s in section_scores)
    max_possible_score = sum(s['max_score'] for s in section_scores)
    total_score_percentage = round((overall_score / max_possible_score * 100), 1) if max_possible_score > 0 else 0
    completion_percentage = float(assessment.completion_percent)
    standard_covered_all = answered_questions >= total_questions and total_questions > 0

    report_code = report.report_code or _report_code(report, company)
    
    return CustomerReportDataResponse(
        report_id=report_code,
        report_uuid=report.id,
        assessment_id=assessment.id,
        customer_name=user.email,
        customer_email=user.email,
        company_name=company.name if company else None,
        company_website=company.website if company else None,
        company_industry=company.industry if company else None,
        company_size=company.size if company else None,
        company_region=company.region if company else None,
        company_country=company.country if company else None,
        company_description=company.description if company else None,
        checklist_title=checklist_title,
        assessment_date=assessment.submitted_at or assessment.created_at,
        report_status=report.status,
        overall_score=overall_score,
        max_possible_score=max_possible_score,
        total_score_percentage=total_score_percentage,
        completion_percentage=completion_percentage,
        total_questions=total_questions,
        answered_questions=answered_questions,
        standard_covered_all=standard_covered_all,
        question_score_distribution=question_score_distribution,
        section_scores=section_scores,
        chapter_data=chapter_data,
        domain_data=domain_data,
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
        question_scores: list[dict] = []
        answered_count = 0
        
        for question in questions:
            max_score += 4  # Maximum score per question is 4 (Yes answer)
            answer = answer_map.get(question.id)
            question_translation = _latest_question_translation(db, question.id)
            question_title = question_translation.question_text if question_translation else question.question_code
            if answer and answer.answer_score is not None:
                total_score += int(answer.answer_score)
                answered_count += 1
            question_score = int(answer.answer_score) if answer and answer.answer_score is not None else 0
            question_scores.append({
                "question_id": question.id,
                "question_code": question.question_code,
                "question_title": question_title,
                "report_domain": question.report_domain,
                "score": question_score,
                "max_score": 4,
                "percentage": round((question_score / 4 * 100), 1) if 4 > 0 else 0,
            })
        
        # Get section translation
        translation = _latest_section_translation(db, section.id)
        section_title = translation.title if translation else section.section_code
        section_domain = next((q.report_domain for q in questions if q.report_domain), None)
        
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        section_scores.append({
            "section_name": section_title,
            "section_title": section_title,
            "section_code": section.section_code,
            "section_domain": section_domain,
            "section_id": section.id,
            "score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 1),
            "question_count": len(questions),
            "answered_question_count": answered_count,
            "question_scores": question_scores,
        })
    
    return section_scores


def _calculate_domain_data(db: Session, assessment: Assessment) -> list[dict]:
    from app.models.checklist import ChecklistQuestion

    questions = db.scalars(
        select(ChecklistQuestion)
        .where(
            ChecklistQuestion.checklist_id == assessment.checklist_id,
            ChecklistQuestion.is_active.is_(True),
        )
    ).all()

    domain_map: dict[str, dict[str, Any]] = {}
    for question in questions:
        domain = question.report_domain or "General"
        domain_item = domain_map.setdefault(
            domain,
            {
                "domain": domain,
                "title": domain,
                "score": 0,
                "max_score": 0,
                "question_count": 0,
            },
        )
        domain_item["question_count"] += 1
        domain_item["max_score"] += 4

    question_ids = [q.id for q in questions]
    answers = db.scalars(
        select(AssessmentAnswer)
        .where(
            AssessmentAnswer.assessment_id == assessment.id,
            AssessmentAnswer.question_id.in_(question_ids),
        )
    ).all()
    answer_map = {a.question_id: a for a in answers}

    for question in questions:
        domain = question.report_domain or "General"
        answer = answer_map.get(question.id)
        if answer and answer.answer_score is not None:
            domain_map[domain]["score"] += int(answer.answer_score)

    domain_data = []
    for domain, data in domain_map.items():
        max_score = data["max_score"]
        domain_data.append({
            "domain": domain,
            "title": data["title"],
            "score": data["score"],
            "max_score": max_score,
            "percentage": round((data["score"] / max_score * 100), 1) if max_score > 0 else 0,
            "question_count": data["question_count"],
        })

    return sorted(domain_data, key=lambda x: x["domain"])


def _calculate_question_distribution(db: Session, assessment: Assessment) -> tuple[list[dict], int, int]:
    from app.models.checklist import ChecklistQuestion

    questions = db.scalars(
        select(ChecklistQuestion)
        .where(
            ChecklistQuestion.checklist_id == assessment.checklist_id,
            ChecklistQuestion.is_active.is_(True),
        )
    ).all()
    total_questions = len(questions)

    question_ids = [q.id for q in questions]
    answers = db.scalars(
        select(AssessmentAnswer)
        .where(
            AssessmentAnswer.assessment_id == assessment.id,
            AssessmentAnswer.question_id.in_(question_ids),
        )
    ).all()
    answer_map = {a.question_id: a for a in answers}

    distribution = {score: 0 for score in range(0, 5)}
    answered_questions = 0
    for question in questions:
        answer = answer_map.get(question.id)
        score = int(answer.answer_score) if answer and answer.answer_score is not None else 0
        if answer and answer.answer_score is not None:
            answered_questions += 1
        distribution[score] += 1

    question_distribution = [
        {
            "score": score,
            "count": count,
            "percentage": round((count / total_questions * 100), 1) if total_questions > 0 else 0,
        }
        for score, count in sorted(distribution.items(), reverse=True)
    ]
    return question_distribution, total_questions, answered_questions


def _latest_question_translation(db: Session, question_id: UUID):
    return db.scalar(
        select(ChecklistQuestionTranslation)
        .where(ChecklistQuestionTranslation.question_id == question_id)
        .order_by(desc(ChecklistQuestionTranslation.created_at))
        .limit(1)
    )


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
            if answer and answer.answer_score is not None:
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
    """Get public admin suggestions for customer from assessment review"""
    # Get the report to find the assessment
    report = db.get(Report, report_id)
    if not report:
        return []
    
    # Get assessment review with answer reviews
    assessment_review = db.scalar(
        select(AssessmentReview)
        .where(AssessmentReview.assessment_id == report.assessment_id)
        .options(selectinload(AssessmentReview.answer_reviews))
    )
    
    if not assessment_review:
        return []
    
    customer_suggestions = []
    for answer_review in assessment_review.answer_reviews:
        # Only include suggestions that are marked as best practices or improvements
        if answer_review.suggestion_type in [SuggestionType.BEST_PRACTICE, SuggestionType.IMPROVEMENT]:
            customer_suggestions.append({
                "suggestion_text": answer_review.suggestion_text,
                "created_at": answer_review.created_at,
                "question_id": str(answer_review.answer.question_id) if answer_review.answer else None
            })
    
    return customer_suggestions
