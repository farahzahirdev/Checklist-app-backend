"""Service layer for customer multi-assessment management."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import distinct, exists, func, select, and_, or_, desc, case
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.assessment import (
    ACCESS_WINDOW_CONSUMING_STATUSES,
    Assessment, 
    AssessmentAnswer, 
    AssessmentStatus, 
    AssessmentEvidenceFile
)
from app.models.user import User
from app.models.checklist import (
    Checklist,
    ChecklistQuestion,
    ChecklistSection,
    ChecklistTranslation,
    ChecklistSectionTranslation,
    ChecklistType,
    ChecklistQuestionTranslation,
)
from app.models.payment import Payment, PaymentStatus
from app.models.report import Report, ReportStatus
from app.models.access_window import AccessWindow
from app.models.reference import Language
from app.schemas.customer_assessments import (
    AssessmentSummary,
    AssessmentDetail,
    AssessmentProgress,
    SectionProgress,
    QuestionSummary,
    CustomerAssessmentListResponse,
    CustomerAssessmentDashboardResponse,
    DashboardSummary,
    AvailableChecklist,
    QuickAction,
    AssessmentActionResponse,
    BulkAssessmentResponse,
    BulkActionResult,
    AssessmentAnalytics,
    MonthlyActivity,
    AssessmentComparison,
)
from app.utils.i18n_messages import translate


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _days_until_expiry(expires_at: datetime) -> int:
    """Calculate days until expiry, negative if already expired."""
    now = _now_utc()
    delta = expires_at - now
    return delta.days


def _report_lookup_for_assessments(db: Session, assessment_ids: list[UUID]) -> dict[UUID, tuple[UUID, ReportStatus, datetime | None]]:
    if not assessment_ids:
        return {}

    rows = db.execute(
        select(Report.assessment_id, Report.id, Report.status, Report.final_pdf_published_at).where(Report.assessment_id.in_(assessment_ids))
    ).all()
    return {
        assessment_id: (report_id, report_status, final_pdf_published_at)
        for assessment_id, report_id, report_status, final_pdf_published_at in rows
    }


def _access_window_lookup(
    db: Session,
    access_window_ids: list[UUID],
) -> dict[UUID, tuple[datetime, datetime, datetime | None]]:
    if not access_window_ids:
        return {}

    rows = db.execute(
        select(
            AccessWindow.id,
            AccessWindow.activated_at,
            AccessWindow.expires_at,
            Payment.paid_at,
        )
        .outerjoin(Payment, Payment.id == AccessWindow.payment_id)
        .where(AccessWindow.id.in_(access_window_ids))
    ).all()

    return {
        access_window_id: (activated_at, expires_at, paid_at)
        for access_window_id, activated_at, expires_at, paid_at in rows
    }


def _language_code_preference_score(lang_code: str, code: str | None) -> int:
    if code == lang_code:
        return 0
    if code == "en":
        return 1
    return 2


def _translation_language_filter(lang_code: str):
    if lang_code == "en":
        return or_(Language.code == "en", Language.id.is_(None))
    return or_(Language.code.in_([lang_code, "en"]), Language.id.is_(None))


def _translation_language_order(lang_code: str):
    return case(
        (Language.code == lang_code, 0),
        (Language.code == "en", 1),
        else_=2,
    )


def _preferred_checklist_translations(
    db: Session,
    checklist_ids: list[UUID],
    lang_code: str,
) -> dict[UUID, ChecklistTranslation]:
    if not checklist_ids:
        return {}

    rows = (
        db.query(ChecklistTranslation, Language.code)
        .join(Language, ChecklistTranslation.language_id == Language.id)
        .filter(ChecklistTranslation.checklist_id.in_(checklist_ids))
        .filter(_translation_language_filter(lang_code))
        .all()
    )

    best: dict[UUID, ChecklistTranslation] = {}
    best_scores: dict[UUID, int] = {}
    for translation, code in rows:
        score = _language_code_preference_score(lang_code, code)
        checklist_id = translation.checklist_id
        if checklist_id not in best_scores or score < best_scores[checklist_id]:
            best_scores[checklist_id] = score
            best[checklist_id] = translation
    return best


def _dedupe_translation_join_rows(rows: list[tuple], lang_code: str, *, entity_index: int = 0) -> list[tuple]:
    best: dict[UUID, tuple] = {}
    best_scores: dict[UUID, int] = {}
    for row in rows:
        entity_id = row[entity_index].id
        language = row[-1]
        code = language.code if language else None
        score = _language_code_preference_score(lang_code, code)
        if entity_id not in best_scores or score < best_scores[entity_id]:
            best_scores[entity_id] = score
            best[entity_id] = row
    return list(best.values())


def get_customer_assessments(
    db: Session, 
    user_id: UUID, 
    *,
    status_filter: Optional[list[AssessmentStatus]] = None,
    checklist_type_filter: Optional[list[str]] = None,
    search: Optional[str] = None,
    sort_by: str = "updated_at",
    sort_order: str = "desc",
    skip: int = 0,
    limit: int = 50,
    lang_code: str = "en"
) -> CustomerAssessmentListResponse:
    """Get customer's assessments with filtering and sorting."""
    
    # Base query without translation join; titles are resolved with language fallback.
    query = (
        db.query(Assessment, Checklist, ChecklistType)
        .join(Checklist, Assessment.checklist_id == Checklist.id)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .filter(Assessment.user_id == user_id)
    )
    
    # Apply filters
    if status_filter:
        # Explicit filter provided — use it as-is.
        query = query.filter(Assessment.status.in_(status_filter))
    
    if checklist_type_filter:
        query = query.filter(ChecklistType.code.in_(checklist_type_filter))
    
    if search:
        search_term = f"%{search}%"
        translated_checklist_ids = (
            select(ChecklistTranslation.checklist_id)
            .join(Language, ChecklistTranslation.language_id == Language.id)
            .where(
                _translation_language_filter(lang_code),
                ChecklistTranslation.title.ilike(search_term),
            )
        )
        query = query.filter(
            or_(
                Checklist.id.in_(translated_checklist_ids),
                ChecklistType.name.ilike(search_term),
                Checklist.version.ilike(search_term),
            )
        )
    
    # Count total DB-backed assessments before pagination.
    total = query.count()
    
    # Apply sorting
    sort_column = Assessment.updated_at
    if sort_by == "created_at":
        sort_column = Assessment.created_at
    elif sort_by == "status":
        sort_column = Assessment.status
    elif sort_by == "completion":
        sort_column = Assessment.completion_percent
    elif sort_by == "expires_at":
        sort_column = Assessment.expires_at
    
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Include synthetic rows for purchases without a persisted assessment:
    # - active access window → not_started (startable)
    # - expired access window, never started → expired (historical, not startable)
    should_include_synthetic_startables = status_filter is None or AssessmentStatus.not_started in status_filter
    should_include_synthetic_expired_unstarted = status_filter is None or AssessmentStatus.expired in status_filter
    should_merge_synthetic_rows = should_include_synthetic_startables or should_include_synthetic_expired_unstarted

    # Apply pagination directly only when synthetic rows are not in play.
    results = query.all() if should_merge_synthetic_rows else query.offset(skip).limit(limit).all()

    report_lookup = _report_lookup_for_assessments(db, [assessment.id for assessment, *_ in results])
    translation_lookup = _preferred_checklist_translations(
        db,
        [checklist.id for _, checklist, _ in results],
        lang_code,
    )
    access_window_lookup = _access_window_lookup(
        db,
        [assessment.access_window_id for assessment, *_ in results],
    )

    # Build response rows from persisted assessments.
    result_assessments = []
    for assessment, checklist, checklist_type in results:
        translation = translation_lookup.get(checklist.id)
        title = translation.title if translation else f"Checklist v{checklist.version}"
        report_details = report_lookup.get(assessment.id)
        access_window_details = access_window_lookup.get(assessment.access_window_id)
        
        result_assessments.append(AssessmentSummary(
            id=assessment.id,
            checklist_id=assessment.checklist_id,
            checklist_title=title,
            checklist_type_code=checklist_type.code,
            checklist_version=f"v{checklist.version}",
            status=assessment.status,
            completion_percent=float(assessment.completion_percent),
            started_at=assessment.started_at,
            submitted_at=assessment.submitted_at,
            expires_at=assessment.expires_at,
            days_until_expiry=_days_until_expiry(assessment.expires_at),
            has_report=report_details is not None,
            report_id=report_details[0] if report_details else None,
            report_status=report_details[1] if report_details else None,
            report_published_at=report_details[2] if report_details else None,
            purchased_at=access_window_details[2] if access_window_details else None,
            access_window_started_at=access_window_details[0] if access_window_details else None,
            access_window_expires_at=access_window_details[1] if access_window_details else assessment.expires_at,
            last_activity=assessment.updated_at,
        ))

    if should_include_synthetic_startables:
        synthetic_startables: list[AssessmentSummary] = []
        available_checklists = _get_available_checklists(db, user_id, lang_code)
        access_window_ids = [c.access_window_id for c in available_checklists if c.access_window_id is not None]
        synthetic_access_window_lookup = _access_window_lookup(db, access_window_ids)

        for checklist in available_checklists:
            if not checklist.can_start or checklist.access_window_id is None:
                continue

            if checklist_type_filter and checklist.checklist_type_code not in checklist_type_filter:
                continue

            if search:
                search_term = search.strip().lower()
                if search_term and search_term not in checklist.title.lower() and search_term not in checklist.checklist_type_name.lower():
                    continue

            access_window_details = synthetic_access_window_lookup.get(checklist.access_window_id)
            if not access_window_details:
                continue

            access_window_start, expires_at, purchased_at = access_window_details

            synthetic_startables.append(
                AssessmentSummary(
                    id=checklist.access_window_id,
                    checklist_id=checklist.checklist_id,
                    checklist_title=checklist.title,
                    checklist_type_code=checklist.checklist_type_code,
                    checklist_version=checklist.version,
                    status=AssessmentStatus.not_started,
                    completion_percent=0,
                    started_at=None,
                    submitted_at=None,
                    expires_at=expires_at,
                    days_until_expiry=_days_until_expiry(expires_at),
                    has_report=False,
                    report_id=None,
                    report_status=None,
                    report_published_at=None,
                    purchased_at=purchased_at,
                    access_window_started_at=access_window_start,
                    access_window_expires_at=expires_at,
                    last_activity=None,
                )
            )

        if synthetic_startables:
            result_assessments.extend(synthetic_startables)

    if should_include_synthetic_expired_unstarted:
        existing_row_ids = {row.id for row in result_assessments}
        for summary in _get_expired_unstarted_access_windows(db, user_id, lang_code):
            if summary.id in existing_row_ids:
                continue
            if checklist_type_filter and summary.checklist_type_code not in checklist_type_filter:
                continue
            if search:
                search_term = search.strip().lower()
                if search_term and search_term not in summary.checklist_title.lower():
                    continue
            result_assessments.append(summary)
            existing_row_ids.add(summary.id)

    if should_merge_synthetic_rows:
        if sort_by == "expires_at":
            result_assessments.sort(
                key=lambda item: item.expires_at,
                reverse=(sort_order == "desc"),
            )
        elif sort_by == "status":
            result_assessments.sort(
                key=lambda item: str(item.status),
                reverse=(sort_order == "desc"),
            )
        elif sort_by == "completion":
            result_assessments.sort(
                key=lambda item: item.completion_percent,
                reverse=(sort_order == "desc"),
            )
        elif sort_by == "created_at":
            result_assessments.sort(
                key=lambda item: item.started_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=(sort_order == "desc"),
            )
        else:
            # Default updated_at-style ordering for mixed persisted/synthetic rows.
            result_assessments.sort(
                key=lambda item: item.last_activity or item.started_at or datetime.min.replace(tzinfo=timezone.utc),
                reverse=(sort_order == "desc"),
            )

        total = len(result_assessments)
        result_assessments = result_assessments[skip: skip + limit]
    
    filters_applied = {
        "status": status_filter,
        "checklist_types": checklist_type_filter,
        "search": search,
    }
    
    return CustomerAssessmentListResponse(
        assessments=result_assessments,
        total=total,
        skip=skip,
        limit=limit,
        has_more=(skip + len(result_assessments)) < total,
        filters_applied=filters_applied if any(filters_applied.values()) else None,
        generated_at=_now_utc(),
    )


def get_assessment_detail(
    db: Session, 
    user_id: UUID, 
    assessment_id: UUID,
    lang_code: str = "en"
) -> AssessmentDetail:
    """Get detailed assessment information."""
    
    # Get assessment with checklist metadata; title resolved with language fallback.
    assessment_data = (
        db.query(Assessment, Checklist, ChecklistType)
        .join(Checklist, Assessment.checklist_id == Checklist.id)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .filter(Assessment.id == assessment_id, Assessment.user_id == user_id)
        .first()
    )
    
    if not assessment_data:
        raise ValueError("Assessment not found")
    
    assessment, checklist, checklist_type = assessment_data
    translation = _preferred_checklist_translations(db, [checklist.id], lang_code).get(checklist.id)
    title = translation.title if translation else f"Checklist v{checklist.version}"
    
    # Get sections and questions for progress calculation
    sections_query = (
        db.query(ChecklistSection)
        .filter(ChecklistSection.checklist_id == checklist.id)
        .all()
    )
    
    questions_query = (
        db.query(ChecklistQuestion)
        .filter(ChecklistQuestion.checklist_id == checklist.id)
        .all()
    )
    
    # Calculate section progress
    total_sections = len(sections_query)
    sections_completed = 0
    
    for section in sections_query:
        section_questions = [q for q in questions_query if q.section_id == section.id]
        answered_questions = (
            db.query(AssessmentAnswer)
            .filter(
                AssessmentAnswer.assessment_id == assessment_id,
                AssessmentAnswer.question_id.in_([q.id for q in section_questions])
            )
            .count()
        )
        if answered_questions == len(section_questions):
            sections_completed += 1
    
    # Estimate time remaining (rough calculation: 2 minutes per unanswered question)
    total_questions = len(questions_query)
    answered_questions = (
        db.query(AssessmentAnswer)
        .filter(AssessmentAnswer.assessment_id == assessment_id)
        .count()
    )
    unanswered_questions = total_questions - answered_questions
    estimated_time_remaining = unanswered_questions * 2 if unanswered_questions > 0 else 0
    
    report = db.scalar(select(Report).where(Report.assessment_id == assessment.id))

    return AssessmentDetail(
        id=assessment.id,
        checklist_id=assessment.checklist_id,
        checklist_title=title,
        checklist_type_code=checklist_type.code,
        checklist_type_name=checklist_type.name,
        checklist_version=f"v{checklist.version}",
        status=assessment.status,
        completion_percent=float(assessment.completion_percent),
        started_at=assessment.started_at,
        submitted_at=assessment.submitted_at,
        expires_at=assessment.expires_at,
        days_until_expiry=_days_until_expiry(assessment.expires_at),
        access_window_id=assessment.access_window_id,
        total_questions=total_questions,
        answered_questions=answered_questions,
        sections_completed=sections_completed,
        total_sections=total_sections,
        estimated_time_remaining_minutes=estimated_time_remaining,
        last_activity=assessment.updated_at,
        report_id=report.id if report else None,
        report_status=report.status if report else None,
    )


def get_assessment_progress(
    db: Session, 
    user_id: UUID, 
    assessment_id: UUID,
    lang_code: str = "en"
) -> AssessmentProgress:
    """Get detailed progress tracking for an assessment."""
    
    # Get assessment first
    assessment = (
        db.query(Assessment)
        .filter(Assessment.id == assessment_id, Assessment.user_id == user_id)
        .first()
    )
    
    if not assessment:
        raise ValueError("Assessment not found")
    
    # Get all answered questions
    answered_questions = (
        db.query(AssessmentAnswer.question_id)
        .filter(AssessmentAnswer.assessment_id == assessment_id)
        .all()
    )
    answered_question_ids = {aq.question_id for aq in answered_questions}
    
    # Get sections and questions with translations
    sections_query = (
        db.query(ChecklistSection, ChecklistSectionTranslation, Language)
        .outerjoin(ChecklistSectionTranslation, ChecklistSection.id == ChecklistSectionTranslation.section_id)
        .outerjoin(Language, ChecklistSectionTranslation.language_id == Language.id)
        .filter(ChecklistSection.checklist_id == assessment.checklist_id)
        .filter(_translation_language_filter(lang_code))
        .order_by(ChecklistSection.display_order, _translation_language_order(lang_code))
        .all()
    )
    sections_query = _dedupe_translation_join_rows(sections_query, lang_code, entity_index=0)
    sections_query.sort(key=lambda row: row[0].display_order)
    
    questions_query = (
        db.query(ChecklistQuestion)
        .filter(ChecklistQuestion.checklist_id == assessment.checklist_id)
        .all()
    )
    
    # Build section progress
    sections_progress = []
    for section, translation, language in sections_query:
        section_questions = [q for q in questions_query if q.section_id == section.id]
        answered_count = len([q for q in section_questions if q.id in answered_question_ids])
        completion = (answered_count / len(section_questions)) * 100 if section_questions else 0
        
        title = translation.title if translation else section.section_code
        
        # Check if section is accessible (previous sections completed)
        is_accessible = True
        if section.display_order > 1:
            prev_sections = [(s, _, _) for s, _, _ in sections_query if s.display_order < section.display_order]
            for prev_section, _, _ in prev_sections:
                prev_questions = [q for q in questions_query if q.section_id == prev_section.id]
                prev_answered = len([q for q in prev_questions if q.id in answered_question_ids])
                if prev_answered < len(prev_questions):
                    is_accessible = False
                    break
        
        sections_progress.append(SectionProgress(
            section_id=section.id,
            section_code=section.section_code,
            section_title=title,
            display_order=section.display_order,
            questions_answered=answered_count,
            total_questions=len(section_questions),
            completion_percent=completion,
            is_accessible=is_accessible,
            is_completed=answered_count == len(section_questions),
        ))
    
    total_answered = len(answered_question_ids)
    total_questions = len(questions_query)
    overall_completion = (total_answered / total_questions) * 100 if total_questions > 0 else 0
    
    # Calculate time spent (simplified - using assessment duration)
    time_spent = 0
    if assessment.started_at:
        time_spent = int((_now_utc() - assessment.started_at).total_seconds() / 60)
    
    # Estimate remaining time
    unanswered = total_questions - total_answered
    estimated_remaining = unanswered * 2 if unanswered > 0 else 0
    
    return AssessmentProgress(
        assessment_id=assessment_id,
        overall_completion=overall_completion,
        sections=sections_progress,
        questions_answered=total_answered,
        total_questions=total_questions,
        time_spent_minutes=time_spent,
        estimated_time_remaining_minutes=estimated_remaining,
    )


def get_customer_dashboard_enhanced(
    db: Session, 
    user_id: UUID,
    lang_code: str = "en"
) -> CustomerAssessmentDashboardResponse:
    """Get enhanced customer dashboard with detailed assessment information."""
    
    # Get summary statistics
    paid_checklists_count = (
        db.scalar(
            select(func.count(distinct(Payment.checklist_id))).where(
                Payment.user_id == user_id,
                Payment.status == PaymentStatus.succeeded,
                Payment.checklist_id.is_not(None),
            )
        ) or 0
    )
    
    active_assessments_count = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
                Assessment.expires_at > _now_utc(),
            )
        ) or 0
    )
    
    submitted_assessments_count = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status == AssessmentStatus.submitted,
            )
        ) or 0
    )
    
    completed_assessments_count = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status == AssessmentStatus.closed,
            )
        ) or 0
    )
    
    expired_assessments_count = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status == AssessmentStatus.expired,
            )
        ) or 0
    )
    
    reports_available = (
        db.scalar(
            select(func.count(Report.id))
            .join(Assessment, Report.assessment_id == Assessment.id)
            .join(User, Assessment.user_id == User.id)
            .where(
                User.id == user_id,
                Report.status == ReportStatus.published,
            )
        ) or 0
    )
    
    # Get active assessments
    active_assessments_query = (
        db.query(Assessment, Checklist, ChecklistType, ChecklistTranslation, Language)
        .join(Checklist, Assessment.checklist_id == Checklist.id)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .outerjoin(ChecklistTranslation, Checklist.id == ChecklistTranslation.checklist_id)
        .outerjoin(Language, ChecklistTranslation.language_id == Language.id)
        .filter(
            Assessment.user_id == user_id,
            Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
            Assessment.expires_at > _now_utc(),
        )
        .filter(_translation_language_filter(lang_code))
        .order_by(Assessment.updated_at.desc(), _translation_language_order(lang_code))
        .limit(10)
        .all()
    )
    active_rows = _dedupe_translation_join_rows(list(active_assessments_query), lang_code, entity_index=0)[:5]
    active_report_lookup = _report_lookup_for_assessments(db, [assessment.id for assessment, *_ in active_rows])

    active_assessments = []
    for assessment, checklist, checklist_type, translation, language in active_rows:
        title = translation.title if translation else f"Checklist v{checklist.version}"
        report_details = active_report_lookup.get(assessment.id)
        
        active_assessments.append(AssessmentSummary(
            id=assessment.id,
            checklist_id=assessment.checklist_id,
            checklist_title=title,
            checklist_type_code=checklist_type.code,
            checklist_version=f"v{checklist.version}",
            status=assessment.status,
            completion_percent=float(assessment.completion_percent),
            started_at=assessment.started_at,
            submitted_at=assessment.submitted_at,
            expires_at=assessment.expires_at,
            days_until_expiry=_days_until_expiry(assessment.expires_at),
            has_report=report_details is not None,
            report_id=report_details[0] if report_details else None,
            report_status=report_details[1] if report_details else None,
            last_activity=assessment.updated_at,
        ))
    
    # Get recent submissions
    recent_submissions_query = (
        db.query(Assessment, Checklist, ChecklistType, ChecklistTranslation, Language)
        .join(Checklist, Assessment.checklist_id == Checklist.id)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .outerjoin(ChecklistTranslation, Checklist.id == ChecklistTranslation.checklist_id)
        .outerjoin(Language, ChecklistTranslation.language_id == Language.id)
        .filter(
            Assessment.user_id == user_id,
            Assessment.status == AssessmentStatus.submitted,
        )
        .filter(_translation_language_filter(lang_code))
        .order_by(Assessment.submitted_at.desc(), _translation_language_order(lang_code))
        .limit(10)
        .all()
    )
    submission_rows = _dedupe_translation_join_rows(list(recent_submissions_query), lang_code, entity_index=0)[:5]
    submission_report_lookup = _report_lookup_for_assessments(db, [assessment.id for assessment, *_ in submission_rows])

    recent_submissions = []
    for assessment, checklist, checklist_type, translation, language in submission_rows:
        title = translation.title if translation else f"Checklist v{checklist.version}"
        report_details = submission_report_lookup.get(assessment.id)
        
        recent_submissions.append(AssessmentSummary(
            id=assessment.id,
            checklist_id=assessment.checklist_id,
            checklist_title=title,
            checklist_type_code=checklist_type.code,
            checklist_version=f"v{checklist.version}",
            status=assessment.status,
            completion_percent=float(assessment.completion_percent),
            started_at=assessment.started_at,
            submitted_at=assessment.submitted_at,
            expires_at=assessment.expires_at,
            days_until_expiry=_days_until_expiry(assessment.expires_at),
            has_report=report_details is not None,
            report_id=report_details[0] if report_details else None,
            report_status=report_details[1] if report_details else None,
            last_activity=assessment.updated_at,
        ))
    
    # Get expiring soon assessments
    seven_days_from_now = _now_utc() + timedelta(days=7)
    expiring_soon_query = (
        db.query(Assessment, Checklist, ChecklistType, ChecklistTranslation, Language)
        .join(Checklist, Assessment.checklist_id == Checklist.id)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .outerjoin(ChecklistTranslation, Checklist.id == ChecklistTranslation.checklist_id)
        .outerjoin(Language, ChecklistTranslation.language_id == Language.id)
        .filter(
            Assessment.user_id == user_id,
            Assessment.expires_at > _now_utc(),
            Assessment.expires_at <= seven_days_from_now,
            Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
        )
        .filter(_translation_language_filter(lang_code))
        .order_by(Assessment.expires_at.asc(), _translation_language_order(lang_code))
        .limit(10)
        .all()
    )
    expiring_rows = _dedupe_translation_join_rows(list(expiring_soon_query), lang_code, entity_index=0)[:5]
    expiring_report_lookup = _report_lookup_for_assessments(db, [assessment.id for assessment, *_ in expiring_rows])

    expiring_soon = []
    for assessment, checklist, checklist_type, translation, language in expiring_rows:
        title = translation.title if translation else f"Checklist v{checklist.version}"
        report_details = expiring_report_lookup.get(assessment.id)
        
        expiring_soon.append(AssessmentSummary(
            id=assessment.id,
            checklist_id=assessment.checklist_id,
            checklist_title=title,
            checklist_type_code=checklist_type.code,
            checklist_version=f"v{checklist.version}",
            status=assessment.status,
            completion_percent=float(assessment.completion_percent),
            started_at=assessment.started_at,
            submitted_at=assessment.submitted_at,
            expires_at=assessment.expires_at,
            days_until_expiry=_days_until_expiry(assessment.expires_at),
            has_report=report_details is not None,
            report_id=report_details[0] if report_details else None,
            report_status=report_details[1] if report_details else None,
            last_activity=assessment.updated_at,
        ))
    
    # Get available checklists
    available_checklists = _get_available_checklists(db, user_id, lang_code)
    
    # Get quick actions
    quick_actions = _generate_quick_actions(active_assessments, available_checklists)
    
    # Calculate completion rate
    total_assessments = (
        db.scalar(
            select(func.count(Assessment.id)).where(Assessment.user_id == user_id)
        ) or 0
    )
    overall_completion_rate = (completed_assessments_count / total_assessments) if total_assessments > 0 else 0
    
    summary = DashboardSummary(
        total_purchased_checklists=paid_checklists_count,
        active_assessments_count=active_assessments_count,
        submitted_assessments_count=submitted_assessments_count,
        completed_assessments_count=completed_assessments_count,
        expired_assessments_count=expired_assessments_count,
        reports_available=reports_available,
        overall_completion_rate=overall_completion_rate,
    )
    
    return CustomerAssessmentDashboardResponse(
        summary=summary,
        active_assessments=active_assessments,
        recent_submissions=recent_submissions,
        expiring_soon=expiring_soon,
        available_checklists=available_checklists,
        quick_actions=quick_actions,
        generated_at=_now_utc(),
    )


def _assessment_consumes_access_window():
    """Assessments linked to an access window that still occupy that purchase slot."""
    return (
        select(Assessment.id)
        .where(
            Assessment.access_window_id == AccessWindow.id,
            Assessment.status.in_(ACCESS_WINDOW_CONSUMING_STATUSES),
        )
        .correlate(AccessWindow)
    )


def _get_available_checklists(db: Session, user_id: UUID, lang_code: str) -> list[AvailableChecklist]:
    """Get checklists available for the customer to start or continue."""

    now = _now_utc()

    # Get purchased checklists with active access windows
    # Join through AccessWindow.checklist_id to ensure we find checklists even if Payment.checklist_id is not set
    purchased_checklists_query = (
        db.query(Checklist, ChecklistType, ChecklistTranslation, Language)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .join(AccessWindow, Checklist.id == AccessWindow.checklist_id)
        .join(Payment, AccessWindow.payment_id == Payment.id)
        .outerjoin(ChecklistTranslation, Checklist.id == ChecklistTranslation.checklist_id)
        .outerjoin(Language, ChecklistTranslation.language_id == Language.id)
        .filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.succeeded,
            AccessWindow.expires_at > now,
            Checklist.status_code_id == 2,  # published
        )
        .filter(_translation_language_filter(lang_code))
        .all()
    )
    purchased_checklists_query = _dedupe_translation_join_rows(
        list(purchased_checklists_query),
        lang_code,
        entity_index=0,
    )

    available = []
    for checklist, checklist_type, translation, language in purchased_checklists_query:
        title = translation.title if translation else f"Checklist v{checklist.version}"

        # Only show startable slots when there is an active access window with no assessment on it yet.
        # A submitted/closed assessment still tied to the window counts as "used" (one purchase = one audit).
        unused_access_windows_count = (
            db.scalar(
                select(func.count(AccessWindow.id))
                .join(Payment, AccessWindow.payment_id == Payment.id)
                .where(
                    Payment.user_id == user_id,
                    AccessWindow.checklist_id == checklist.id,
                    AccessWindow.expires_at > now,
                    ~exists(_assessment_consumes_access_window()),
                )
            )
            or 0
        )

        if unused_access_windows_count == 0:
            continue

        has_active_assessment = (
            db.scalar(
                select(func.count(Assessment.id)).where(
                    Assessment.user_id == user_id,
                    Assessment.checklist_id == checklist.id,
                    Assessment.expires_at > now,
                    Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
                )
            )
            or 0
        ) > 0

        access_window = (
            db.query(AccessWindow)
            .join(Payment, AccessWindow.payment_id == Payment.id)
            .filter(
                Payment.user_id == user_id,
                AccessWindow.checklist_id == checklist.id,
                AccessWindow.expires_at > now,
                ~exists(_assessment_consumes_access_window()),
            )
            .first()
        )

        available.append(AvailableChecklist(
            checklist_id=checklist.id,
            title=title,
            checklist_type_code=checklist_type.code,
            checklist_type_name=checklist_type.name,
            version=f"v{checklist.version}",
            description=translation.description if translation else None,
            estimated_duration_minutes=None,
            price_cents=0,  # Already purchased
            currency="USD",
            is_purchased=True,
            can_start=not has_active_assessment,
            access_window_id=access_window.id if access_window else None,
        ))

    return available


def _get_expired_unstarted_access_windows(
    db: Session,
    user_id: UUID,
    lang_code: str,
) -> list[AssessmentSummary]:
    """Purchases whose access window lapsed before the customer started an assessment."""
    now = _now_utc()
    rows = (
        db.query(AccessWindow, Checklist, ChecklistType)
        .join(Payment, AccessWindow.payment_id == Payment.id)
        .join(Checklist, AccessWindow.checklist_id == Checklist.id)
        .join(ChecklistType, Checklist.checklist_type_id == ChecklistType.id)
        .filter(
            Payment.user_id == user_id,
            Payment.status == PaymentStatus.succeeded,
            AccessWindow.checklist_id.is_not(None),
            AccessWindow.expires_at <= now,
            ~exists(_assessment_consumes_access_window()),
        )
        .order_by(desc(AccessWindow.expires_at))
        .all()
    )

    if not rows:
        return []

    translation_lookup = _preferred_checklist_translations(
        db,
        [checklist.id for _, checklist, _ in rows],
        lang_code,
    )
    access_window_lookup = _access_window_lookup(db, [aw.id for aw, _, _ in rows])

    summaries: list[AssessmentSummary] = []
    for access_window, checklist, checklist_type in rows:
        translation = translation_lookup.get(checklist.id)
        title = translation.title if translation else f"Checklist v{checklist.version}"
        access_window_details = access_window_lookup.get(access_window.id)
        if not access_window_details:
            continue
        access_window_start, expires_at, purchased_at = access_window_details
        summaries.append(
            AssessmentSummary(
                id=access_window.id,
                checklist_id=checklist.id,
                checklist_title=title,
                checklist_type_code=checklist_type.code,
                checklist_version=f"v{checklist.version}",
                status=AssessmentStatus.expired,
                completion_percent=0,
                started_at=None,
                submitted_at=None,
                expires_at=expires_at,
                days_until_expiry=_days_until_expiry(expires_at),
                has_report=False,
                report_id=None,
                report_status=None,
                report_published_at=None,
                purchased_at=purchased_at,
                access_window_started_at=access_window_start,
                access_window_expires_at=expires_at,
                last_activity=expires_at,
            )
        )
    return summaries


def _generate_quick_actions(active_assessments: list[AssessmentSummary], available_checklists: list[AvailableChecklist]) -> list[QuickAction]:
    """Generate quick actions for the customer dashboard."""
    
    actions = []
    
    # Action to resume most recent active assessment
    if active_assessments:
        most_recent = active_assessments[0]
        actions.append(QuickAction(
            action_id="resume_latest",
            action_type="resume_assessment",
            label=f"Resume {most_recent.checklist_title}",
            description="Continue working on your most recent assessment",
            assessment_id=most_recent.id,
            checklist_id=None,
            is_enabled=True,
            priority=1,
        ))
    
    # Action to start new assessment
    startable_checklists = [c for c in available_checklists if c.can_start]
    if startable_checklists:
        checklist = startable_checklists[0]
        actions.append(QuickAction(
            action_id="start_new",
            action_type="start_assessment",
            label=f"Start {checklist.title}",
            description="Begin a new assessment",
            assessment_id=None,
            checklist_id=checklist.checklist_id,
            is_enabled=True,
            priority=2,
        ))
    
    # Action to view all assessments
    actions.append(QuickAction(
        action_id="view_all",
        action_type="view_assessments",
        label="View All Assessments",
        description="See all your assessments and their status",
        assessment_id=None,
        checklist_id=None,
        is_enabled=True,
        priority=3,
    ))
    
    return actions


def perform_assessment_action(
    db: Session,
    user_id: UUID,
    assessment_id: UUID,
    action: str,
    reason: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AssessmentActionResponse:
    """Perform an action on an assessment (pause, resume, extend, etc.)."""
    
    assessment = (
        db.query(Assessment)
        .filter(Assessment.id == assessment_id, Assessment.user_id == user_id)
        .first()
    )
    
    if not assessment:
        raise ValueError("Assessment not found")
    
    old_status = assessment.status
    new_expires_at = None
    
    if action == "pause":
        if assessment.status != AssessmentStatus.in_progress:
            raise ValueError("Only in-progress assessments can be paused")
        # Note: We don't have a paused status, so this might need to be implemented
        # For now, we'll just return a message
        return AssessmentActionResponse(
            success=False,
            message="Pause functionality not yet implemented",
            assessment_id=assessment_id,
            action_performed=action,
            new_status=None,
            updated_expires_at=None,
        )
    
    elif action == "resume":
        if assessment.status != AssessmentStatus.not_started:
            raise ValueError("Only not-started assessments can be resumed")
        assessment.status = AssessmentStatus.in_progress
        if not assessment.started_at:
            assessment.started_at = _now_utc()
    
    elif action == "extend":
        # Extend expiry by 7 days
        assessment.expires_at = assessment.expires_at + timedelta(days=7)
        new_expires_at = assessment.expires_at
    
    elif action == "archive":
        if assessment.status not in [AssessmentStatus.submitted, AssessmentStatus.closed]:
            raise ValueError("Only submitted or closed assessments can be archived")
        # Note: We don't have an archived status, this would need to be implemented
        return AssessmentActionResponse(
            success=False,
            message="Archive functionality not yet implemented",
            assessment_id=assessment_id,
            action_performed=action,
            new_status=None,
            updated_expires_at=None,
        )
    
    else:
        raise ValueError(f"Unknown action: {action}")
    
    db.commit()
    
    return AssessmentActionResponse(
        success=True,
        message=f"Assessment {action}d successfully",
        assessment_id=assessment_id,
        action_performed=action,
        new_status=assessment.status,
        updated_expires_at=new_expires_at,
    )


def perform_bulk_assessment_action(
    db: Session,
    user_id: UUID,
    assessment_ids: list[UUID],
    action: str,
    parameters: Optional[dict] = None
) -> BulkAssessmentResponse:
    """Perform bulk actions on multiple assessments."""
    
    results = []
    success_count = 0
    failure_count = 0
    
    for assessment_id in assessment_ids:
        try:
            # For extend action, we can use the existing function
            if action == "extend":
                response = perform_assessment_action(db, user_id, assessment_id, action)
                results.append(BulkActionResult(
                    assessment_id=assessment_id,
                    success=response.success,
                    message=response.message,
                    new_status=response.new_status,
                ))
                if response.success:
                    success_count += 1
                else:
                    failure_count += 1
            else:
                # Other actions would need to be implemented
                results.append(BulkActionResult(
                    assessment_id=assessment_id,
                    success=False,
                    message=f"Bulk action '{action}' not yet implemented",
                    new_status=None,
                ))
                failure_count += 1
        except Exception as e:
            results.append(BulkActionResult(
                assessment_id=assessment_id,
                success=False,
                message=str(e),
                new_status=None,
            ))
            failure_count += 1
    
    summary = f"Bulk {action} completed: {success_count} succeeded, {failure_count} failed"
    
    return BulkAssessmentResponse(
        success_count=success_count,
        failure_count=failure_count,
        results=results,
        summary=summary,
    )


def get_assessment_analytics(
    db: Session,
    user_id: UUID,
    lang_code: str = "en"
) -> AssessmentAnalytics:
    """Get analytics for customer's assessment performance."""
    
    # Get basic counts
    total_assessments = (
        db.scalar(
            select(func.count(Assessment.id)).where(Assessment.user_id == user_id)
        ) or 0
    )
    
    completed_assessments = (
        db.scalar(
            select(func.count(Assessment.id)).where(
                Assessment.user_id == user_id,
                Assessment.status == AssessmentStatus.closed,
            )
        ) or 0
    )
    
    completion_rate = (completed_assessments / total_assessments) if total_assessments > 0 else 0
    
    # Get average time to completion
    avg_completion_time = (
        db.scalar(
            select(func.avg(
                func.extract('epoch', Assessment.submitted_at - Assessment.started_at) / 86400
            ))
            .where(
                Assessment.user_id == user_id,
                Assessment.status == AssessmentStatus.closed,
                Assessment.started_at.is_not(None),
                Assessment.submitted_at.is_not(None),
            )
        ) or 0
    )
    
    # Get most active checklist type
    most_active_type = (
        db.query(ChecklistType.code, func.count(Assessment.id).label('count'))
        .join(Checklist, ChecklistType.id == Checklist.checklist_type_id)
        .join(Assessment, Checklist.id == Assessment.checklist_id)
        .filter(Assessment.user_id == user_id)
        .group_by(ChecklistType.code)
        .order_by(func.count(Assessment.id).desc())
        .first()
    )
    
    most_active_checklist_type = most_active_type[0] if most_active_type else None
    
    # Get monthly activity for last 12 months
    monthly_activity = []
    for i in range(12):
        month_date = _now_utc() - timedelta(days=30 * i)
        month_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(microseconds=1)
        
        started = (
            db.scalar(
                select(func.count(Assessment.id)).where(
                    Assessment.user_id == user_id,
                    Assessment.started_at >= month_start,
                    Assessment.started_at <= month_end,
                )
            ) or 0
        )
        
        completed = (
            db.scalar(
                select(func.count(Assessment.id)).where(
                    Assessment.user_id == user_id,
                    Assessment.status == AssessmentStatus.closed,
                    Assessment.submitted_at >= month_start,
                    Assessment.submitted_at <= month_end,
                )
            ) or 0
        )
        
        submitted = (
            db.scalar(
                select(func.count(Assessment.id)).where(
                    Assessment.user_id == user_id,
                    Assessment.status == AssessmentStatus.submitted,
                    Assessment.submitted_at >= month_start,
                    Assessment.submitted_at <= month_end,
                )
            ) or 0
        )
        
        monthly_activity.append(MonthlyActivity(
            month=month_date.strftime("%B"),
            year=month_date.year,
            assessments_started=started,
            assessments_completed=completed,
            assessments_submitted=submitted,
        ))
    
    # For now, placeholder values for improvement areas and strengths
    # These would need more sophisticated analysis based on assessment performance
    improvement_areas = ["Time management", "Documentation completeness"]
    strengths = ["Technical compliance", "Security practices"]
    
    return AssessmentAnalytics(
        total_assessments=total_assessments,
        completion_rate=completion_rate,
        average_score=None,  # Would need scoring implementation
        average_time_to_completion_days=avg_completion_time,
        most_active_checklist_type=most_active_checklist_type,
        improvement_areas=improvement_areas,
        strengths=strengths,
        monthly_activity=monthly_activity,
        generated_at=_now_utc(),
    )
