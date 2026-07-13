from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.services.company_context import resolve_company_id, user_has_company_access
from app.services.settings_manager import get_runtime_int
from app.models.access_window import AccessWindow
from app.models.assessment import (
    ACCESS_WINDOW_CONSUMING_STATUSES,
    AnswerChoice,
    Assessment,
    AssessmentAnswer,
    AssessmentEvidenceFile,
    AssessmentStatus,
    PriorityLevel,
)
from app.models.checklist import (
    Checklist,
    ChecklistQuestion,
    ChecklistQuestionTranslation,
    ChecklistSection,
    ChecklistSectionTranslation,
    ChecklistStatus,
    ChecklistTranslation,
    SeverityLevel,
)
from app.models.payment import Payment, PaymentStatus
from app.models.reference import Language
from app.models.user import User, UserRole
from app.utils.i18n import DEFAULT_LANGUAGE_CODE
from app.utils.audit_logger import AuditLogger
from app.schemas.assessment import (
    AssessmentAnswerOptionResponse,
    AssessmentAnswerResponse,
    AssessmentDetailResponse,
    AssessmentQuestionResponse,
    AssessmentSectionResponse,
    AssessmentSessionResponse,
    AssessmentSubmitResponse,
)
from app.utils.i18n_messages import translate
from app.utils.html_sanitizer import sanitize_html
from app.schemas.admin_checklist import EvidenceRuleResponse
from app.services.notifications import NotificationService, NotificationEventType, NotificationEvent
from app.services.settings_manager import get_runtime_int


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _log_assessment_audit(
    db: Session,
    *,
    action: str,
    assessment: Assessment,
    actor_user_id: UUID,
    changes_summary: str,
    after_data: dict | None = None,
) -> None:
    try:
        AuditLogger.log_assessment_action(
            db=db,
            action=action,
            assessment_id=assessment.id,
            actor_user_id=actor_user_id,
            changes_summary=changes_summary,
            after_data=after_data,
        )
    except Exception as e:
        print(f"Error creating audit log for assessment {assessment.id}: {e}")


def _serialize_assessment(assessment: Assessment, *, is_new: bool) -> AssessmentSessionResponse:
    return AssessmentSessionResponse(
        assessment_id=assessment.id,
        checklist_id=assessment.checklist_id,
        user_id=assessment.user_id,
        access_window_id=assessment.access_window_id,
        company_id=assessment.company_id,
        status=assessment.status,
        started_at=assessment.started_at,
        expires_at=assessment.expires_at,
        completion_percent=float(assessment.completion_percent),
        is_new=is_new,
    )


def _latest_succeeded_payment(db: Session, *, user_id: UUID, checklist_id: UUID, company_id: UUID | None = None) -> Payment | None:
    query = select(Payment).where(
        Payment.user_id == user_id,
        Payment.checklist_id == checklist_id,
        Payment.status == PaymentStatus.succeeded,
    )
    if company_id is not None:
        query = query.where(Payment.company_id == company_id)
    return db.scalar(query.order_by(desc(Payment.paid_at), desc(Payment.created_at)))


def _active_access_window(
    db: Session,
    *,
    user_id: UUID,
    checklist_id: UUID,
    now: datetime,
    company_id: UUID | None = None,
) -> AccessWindow | None:
    """
    Get the most recent active access window for the user that hasn't been
    used for an assessment yet (one purchase = one audit run).
    """
    if hasattr(db, "query"):
        # Get active access windows (not expired)
        access_window_query = (
            db.query(AccessWindow)
            .outerjoin(Payment, AccessWindow.payment_id == Payment.id)
            .filter(AccessWindow.user_id == user_id, AccessWindow.expires_at > now)
            .filter(
                or_(
                    AccessWindow.checklist_id == checklist_id,
                    and_(AccessWindow.checklist_id.is_(None), Payment.checklist_id == checklist_id),
                    and_(AccessWindow.payment_id.is_(None), AccessWindow.checklist_id.is_(None)),
                )
            )
        )
        if company_id is not None:
            access_window_query = access_window_query.filter(AccessWindow.company_id == company_id)
        access_windows = access_window_query.order_by(desc(AccessWindow.expires_at)).all()
    else:
        payments_by_id = {p.id: p for p in getattr(db, "payments", [])}
        access_windows = []
        for aw in getattr(db, "access_windows", []):
            if aw.user_id != user_id or aw.expires_at <= now:
                continue
            if company_id is not None and aw.company_id != company_id:
                continue

            payment = payments_by_id.get(aw.payment_id)
            checklist_matches = (
                aw.checklist_id == checklist_id
                or (aw.checklist_id is None and payment is not None and payment.checklist_id == checklist_id)
                or (aw.payment_id is None and aw.checklist_id is None)
            )
            if checklist_matches:
                access_windows.append(aw)

        access_windows.sort(key=lambda item: item.expires_at, reverse=True)
    
    # Check each access window to see if it already has an assessment on it.
    for aw in access_windows:
        if hasattr(db, "assessments"):
            consuming_assessment = next(
                (
                    item
                    for item in db.assessments
                    if item.access_window_id == aw.id and item.status in ACCESS_WINDOW_CONSUMING_STATUSES
                ),
                None,
            )
        else:
            consuming_assessment = db.scalar(
                select(Assessment).where(
                    Assessment.access_window_id == aw.id,
                    Assessment.status.in_(ACCESS_WINDOW_CONSUMING_STATUSES),
                )
            )
        if consuming_assessment is None:
            return aw
    
    return None


def _ensure_access_window(
    db: Session,
    *,
    user: User,
    checklist_id: UUID,
    payment: Payment | None,
    now: datetime,
    company_id: UUID | None = None,
) -> AccessWindow:
    settings = get_settings()
    existing = _active_access_window(
        db,
        user_id=user.id,
        checklist_id=checklist_id,
        now=now,
        company_id=company_id,
    )
    if existing is not None:
        if existing.checklist_id is None:
            existing.checklist_id = checklist_id
        return existing

    access_window = AccessWindow(
        user_id=user.id,
        payment_id=payment.id if payment else None,
        checklist_id=checklist_id,
        company_id=company_id,
        activated_at=now,
        expires_at=now + timedelta(days=get_runtime_int(db, "assessment_completion_days", settings.assessment_completion_days)),
    )
    db.add(access_window)
    db.flush()
    return access_window


def _get_active_assessment(
    db: Session, *, user: User, checklist_id: UUID | None = None, company_id: UUID | None = None, lang_code: str = "en"
) -> Assessment:
    now = _now_utc()
    conditions = [Assessment.user_id == user.id, Assessment.expires_at > now]
    if checklist_id is not None:
        conditions.append(Assessment.checklist_id == checklist_id)
    if company_id is not None:
        conditions.append(Assessment.company_id == company_id)
    assessment = db.scalar(
        select(Assessment)
        .where(*conditions)
        .where(Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]))
        .order_by(desc(Assessment.created_at))
    )
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("assessment_not_found", lang_code))
    return assessment


def get_current_assessment(db: Session, *, user: User, checklist_id: UUID | None = None, company_id: UUID | None = None, lang_code: str | None = None) -> AssessmentSessionResponse:
    assessment = _get_active_assessment(db, user=user, checklist_id=checklist_id, company_id=company_id)
    return _serialize_assessment(assessment, is_new=False)


def start_assessment(
    db: Session, *, user: User, checklist_id: UUID, company_id: UUID | None = None, lang_code: str = "en"
) -> AssessmentSessionResponse:
    now = _now_utc()
    settings = get_settings()
    completion_days = get_runtime_int(db, "assessment_completion_days", settings.assessment_completion_days)
    company_id = resolve_company_id(user, company_id)

    if user.role != UserRole.admin and company_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("profile_completion_required", lang_code),
        )

    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
    if checklist.status != ChecklistStatus.published:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("checklist_not_published", lang_code))
    
    # Check for existing assessment in progress (can resume)
    existing_query = select(Assessment).where(
        Assessment.user_id == user.id,
        Assessment.checklist_id == checklist_id,
        Assessment.expires_at > now,
        Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
    )
    if company_id is not None:
        existing_query = existing_query.where(Assessment.company_id == company_id)
    existing = db.scalar(existing_query.order_by(desc(Assessment.created_at)))
    if existing is not None:
        if existing.status == AssessmentStatus.not_started:
            # Start is the activation point for the 7-day completion lifecycle.
            existing.status = AssessmentStatus.in_progress
            existing.started_at = now
            existing.expires_at = now + timedelta(days=completion_days)
            db.add(existing)
            db.commit()
            db.refresh(existing)

            _log_assessment_audit(
                db,
                action="assessment_start",
                assessment=existing,
                actor_user_id=user.id,
                changes_summary=f"Started existing not-started assessment for checklist {checklist_id}",
                after_data={"checklist_id": str(checklist_id), "status": str(existing.status)},
            )

            # Send notification only on activation transition.
            try:
                event = NotificationEvent(
                    event_type=NotificationEventType.ASSESSMENT_STARTED,
                    user_id=user.id,
                    assessment_id=existing.id,
                    lang_code=lang_code,
                    context={"access_window_days": completion_days},
                )
                notification_service = NotificationService(db)
                notification_service.notify(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send assessment_started notification: {e}", exc_info=True)

        return _serialize_assessment(existing, is_new=False)

    if user.role == UserRole.admin:
        access_window = _ensure_access_window(
            db,
            user=user,
            checklist_id=checklist_id,
            payment=None,
            now=now,
            company_id=company_id,
        )
    else:
        payment = _latest_succeeded_payment(db, user_id=user.id, checklist_id=checklist_id, company_id=company_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("payment_required", lang_code))

        if not user_has_company_access(db, user=user, company_id=company_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("forbidden", lang_code))

        access_window = _active_access_window(
            db,
            user_id=user.id,
            checklist_id=checklist_id,
            now=now,
            company_id=company_id,
        )
        if access_window is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate("assessment_already_submitted_with_this_payment", lang_code),
            )
    
    assessment = Assessment(
        user_id=user.id,
        checklist_id=checklist_id,
        company_id=company_id,
        access_window_id=access_window.id,
        started_at=now,
        status=AssessmentStatus.in_progress,
        expires_at=now + timedelta(days=completion_days),
        completion_percent=0,
    )
    db.add(assessment)
    db.flush()
    db.commit()
    db.refresh(assessment)

    _log_assessment_audit(
        db,
        action="assessment_create",
        assessment=assessment,
        actor_user_id=user.id,
        changes_summary=f"Started assessment for checklist {checklist_id}",
        after_data={"checklist_id": str(checklist_id), "status": str(assessment.status)},
    )
    
    # Send notification
    try:
        event = NotificationEvent(
            event_type=NotificationEventType.ASSESSMENT_STARTED,
            user_id=user.id,
            assessment_id=assessment.id,
            lang_code=lang_code,
            context={"access_window_days": completion_days},
        )
        notification_service = NotificationService(db)
        notification_service.notify(event)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send assessment_started notification: {e}", exc_info=True)

    return _serialize_assessment(assessment, is_new=True)


ANSWER_SCORES: dict[AnswerChoice, int] = {
    AnswerChoice.four: 4,
    AnswerChoice.three: 3,
    AnswerChoice.two: 2,
    AnswerChoice.one: 1,
}


def _get_owned_active_assessment(
    db: Session, *, user: User, assessment_id: UUID, company_id: UUID | None = None, lang_code: str = "en"
) -> Assessment:
    query = select(Assessment).where(Assessment.id == assessment_id, Assessment.user_id == user.id)
    if company_id is not None:
        query = query.where(Assessment.company_id == company_id)
    assessment = db.scalar(query)
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("assessment_not_found", lang_code))
    if assessment.status in {AssessmentStatus.submitted, AssessmentStatus.closed, AssessmentStatus.expired}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("assessment_not_editable", lang_code))
    if assessment.expires_at <= _now_utc():
        assessment.status = AssessmentStatus.expired
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("assessment_expired", lang_code))
    return assessment


def _question_for_assessment(
    db: Session, *, assessment: Assessment, question_id: UUID, lang_code: str = "en"
) -> ChecklistQuestion:
    question = db.scalar(
        select(ChecklistQuestion).where(
            ChecklistQuestion.id == question_id,
            ChecklistQuestion.checklist_id == assessment.checklist_id,
            ChecklistQuestion.is_active.is_(True),
        )
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("question_not_found", lang_code))
    return question


def _priority_for_choice(choice: AnswerChoice) -> PriorityLevel:
    if choice == AnswerChoice.one:
        return PriorityLevel.high
    if choice == AnswerChoice.two:
        return PriorityLevel.medium
    return PriorityLevel.low


def _severity_to_points(severity: SeverityLevel) -> int:
    if severity == SeverityLevel.high:
        return 4
    if severity == SeverityLevel.medium:
        return 3
    return 1


def _recompute_completion(db: Session, *, assessment: Assessment) -> float:
    total_questions = db.scalar(
        select(func.count(ChecklistQuestion.id)).where(
            ChecklistQuestion.checklist_id == assessment.checklist_id,
            ChecklistQuestion.is_active.is_(True),
        )
    )
    answered_count = db.scalar(select(func.count(AssessmentAnswer.id)).where(AssessmentAnswer.assessment_id == assessment.id))

    if not total_questions:
        completion = 0.0
    else:
        completion = round((answered_count / total_questions) * 100, 2)

    assessment.completion_percent = completion
    return completion


def _default_language(db: Session) -> Language | None:
    return db.scalar(
        select(Language).where(Language.is_default.is_(True), Language.is_active.is_(True)).limit(1)
    ) or db.scalar(select(Language).where(Language.code == DEFAULT_LANGUAGE_CODE, Language.is_active.is_(True)).limit(1))


def _language_by_code(db: Session, lang_code: str | None) -> Language | None:
    if not lang_code:
        return None
    return db.scalar(select(Language).where(Language.code == lang_code, Language.is_active.is_(True)))


def _latest_checklist_translation(db: Session, checklist_id: UUID) -> ChecklistTranslation | None:
    return db.scalar(
        select(ChecklistTranslation)
        .where(ChecklistTranslation.checklist_id == checklist_id)
        .order_by(ChecklistTranslation.created_at.desc())
        .limit(1)
    )


def _latest_section_translation(db: Session, section_id: UUID) -> ChecklistSectionTranslation | None:
    return db.scalar(
        select(ChecklistSectionTranslation)
        .where(ChecklistSectionTranslation.section_id == section_id)
        .order_by(ChecklistSectionTranslation.created_at.desc())
        .limit(1)
    )


def _latest_question_translation(db: Session, question_id: UUID) -> ChecklistQuestionTranslation | None:
    return db.scalar(
        select(ChecklistQuestionTranslation)
        .where(ChecklistQuestionTranslation.question_id == question_id)
        .order_by(ChecklistQuestionTranslation.created_at.desc())
        .limit(1)
    )


def _translation_for_language(
    db: Session,
    *,
    requested_lang_code: str | None,
    fetch_for_language_id,
    fetch_latest,
):
    """Resolve translation: requested language, then default language, then latest row."""
    requested = _language_by_code(db, requested_lang_code)
    if requested is not None:
        translation = fetch_for_language_id(requested.id)
        if translation is not None:
            return translation

    default_language = _default_language(db)
    if default_language is not None and (requested is None or default_language.id != requested.id):
        translation = fetch_for_language_id(default_language.id)
        if translation is not None:
            return translation

    return fetch_latest()


def _checklist_translation_for_language(
    db: Session, checklist_id: UUID, lang_code: str | None
) -> ChecklistTranslation | None:
    return _translation_for_language(
        db,
        requested_lang_code=lang_code,
        fetch_for_language_id=lambda language_id: db.scalar(
            select(ChecklistTranslation).where(
                ChecklistTranslation.checklist_id == checklist_id,
                ChecklistTranslation.language_id == language_id,
            )
        ),
        fetch_latest=lambda: _latest_checklist_translation(db, checklist_id),
    )


def _section_translation_for_language(
    db: Session, section_id: UUID, lang_code: str | None
) -> ChecklistSectionTranslation | None:
    return _translation_for_language(
        db,
        requested_lang_code=lang_code,
        fetch_for_language_id=lambda language_id: db.scalar(
            select(ChecklistSectionTranslation).where(
                ChecklistSectionTranslation.section_id == section_id,
                ChecklistSectionTranslation.language_id == language_id,
            )
        ),
        fetch_latest=lambda: _latest_section_translation(db, section_id),
    )


_DEFAULT_ANSWER_LABELS: dict[int, str] = {
    4: "Yes",
    3: "Partially",
    2: "No",
    1: "Don't know",
}


def _guidance_for_score(translation: ChecklistQuestionTranslation | None, score: int) -> str | None:
    if translation is None:
        return None
    guidance_by_score = {
        4: translation.guidance_score_4,
        3: translation.guidance_score_3,
        2: translation.guidance_score_2,
        1: translation.guidance_score_1,
    }
    value = guidance_by_score.get(score)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _translation_answer_option_overrides(
    translation: ChecklistQuestionTranslation | None,
) -> dict[int, dict[str, str | None]]:
    if translation is None or not translation.answer_options:
        return {}
    overrides: dict[int, dict[str, str | None]] = {}
    for item in translation.answer_options:
        if not isinstance(item, dict):
            continue
        position = item.get("position")
        if not isinstance(position, int):
            continue
        overrides[position] = {
            "label": item.get("label"),
            "description": item.get("description"),
        }
    return overrides


def _answer_options_for_assessment(
    question: ChecklistQuestion,
    translation: ChecklistQuestionTranslation | None,
) -> list[AssessmentAnswerOptionResponse]:
    overrides = _translation_answer_option_overrides(translation)
    db_options = sorted(getattr(question, "answer_options", []) or [], key=lambda option: option.position)

    if db_options:
        responses: list[AssessmentAnswerOptionResponse] = []
        for option in db_options:
            override = overrides.get(option.position, {})
            override_label = override.get("label")
            override_description = override.get("description")
            label = (override_label if override_label else None) or option.label
            description = (
                (override_description if override_description else None)
                or (option.description.strip() if option.description else None)
                or _guidance_for_score(translation, option.score)
            )
            responses.append(
                AssessmentAnswerOptionResponse(
                    position=option.position,
                    label=label,
                    score=option.score,
                    choice_code=option.choice_code,
                    description=description,
                )
            )
        return responses

    # No persisted options — synthesize the standard four choices from translation guidance.
    synthesized: list[AssessmentAnswerOptionResponse] = []
    for position, score in enumerate([4, 3, 2, 1], start=1):
        override = overrides.get(position, {})
        label = override.get("label") or _DEFAULT_ANSWER_LABELS[score]
        description = override.get("description") or _guidance_for_score(translation, score)
        synthesized.append(
            AssessmentAnswerOptionResponse(
                position=position,
                label=label,
                score=score,
                choice_code=None,
                description=description,
            )
        )
    return synthesized


def _question_translation_for_language(
    db: Session, question_id: UUID, lang_code: str | None
) -> ChecklistQuestionTranslation | None:
    return _translation_for_language(
        db,
        requested_lang_code=lang_code,
        fetch_for_language_id=lambda language_id: db.scalar(
            select(ChecklistQuestionTranslation).where(
                ChecklistQuestionTranslation.question_id == question_id,
                ChecklistQuestionTranslation.language_id == language_id,
            )
        ),
        fetch_latest=lambda: _latest_question_translation(db, question_id),
    )


def _to_assessment_question_response(
    question: ChecklistQuestion,
    answer_map: dict[UUID, AssessmentAnswer],
    children_map: dict[UUID, list[ChecklistQuestion]],
    db: Session,
    assessment: Assessment,
    lang_code: str | None = None,
) -> 'AssessmentQuestionResponse':
    translation = _question_translation_for_language(db, question.id, lang_code)
    customer_answer = None
    customer_answer_status = "not_started"
    answer = answer_map.get(question.id)
    if answer is not None and answer.answer is not None:
        customer_answer = answer.answer
        customer_answer_status = "answered"

    sub_questions = [
        _to_assessment_question_response(subq, answer_map, children_map, db, assessment, lang_code)
        for subq in sorted(children_map.get(question.id, []), key=lambda q: q.display_order)
    ]

    # Get admin note (pre-populated by admin) and add evidence guidance
    admin_note = question.note_for_user
    if question.evidence_enabled:
        evidence_note = "Upload supporting evidence to strengthen your assessment (PDF, PNG, JPG - max 10MB). You can upload evidence before or after answering the question."
        if admin_note:
            admin_note = f"{admin_note}\n\n{evidence_note}"
        else:
            admin_note = evidence_note

    # Get user note (added during assessment)
    user_note = None
    answer = answer_map.get(question.id)
    if answer is not None and answer.note_text:
        user_note = answer.note_text

    # Get evidence files for this question
    evidence_files = []
    # Query evidence files by both answer_id and question_id
    evidence_query = select(AssessmentEvidenceFile).where(
        AssessmentEvidenceFile.assessment_id == assessment.id,
        AssessmentEvidenceFile.question_id == question.id,
        AssessmentEvidenceFile.deleted_at.is_(None)
    )
    
    # If there's an answer, also include files linked to the answer
    if answer is not None:
        evidence_query = evidence_query.where(
            (AssessmentEvidenceFile.answer_id == answer.id) |
            (AssessmentEvidenceFile.answer_id.is_(None))
        )
    else:
        # If no answer, only get files not linked to an answer
        evidence_query = evidence_query.where(AssessmentEvidenceFile.answer_id.is_(None))
    
    evidence_files = db.scalars(
        evidence_query.order_by(AssessmentEvidenceFile.uploaded_at.desc())
    ).all()

    legal_title = (translation.legal_requirement_title or "").strip() if translation else ""
    legal_description = (translation.legal_requirement_description or "").strip() if translation else ""
    question_text = (translation.question_text or "").strip() if translation else ""
    paragraph_title = (translation.paragraph_title or "").strip() if translation else ""

    # Prefer dedicated legal fields from the admin editor / Excel "Legal Requirement" column.
    # Do not use question_text here — that is the customer-facing paragraph/question text.
    legal_requirement = legal_description or legal_title or ""
    if legal_requirement:
        legal_requirement = sanitize_html(legal_requirement)

    # Heading: dedicated paragraph title, or Excel question text when it is not just a copy
    # of the legal requirement title (admin currently stores legal title in question_text).
    question_title = paragraph_title or None
    if not question_title and question_text:
        if question_text != legal_title:
            question_title = question_text
        elif legal_description and question_text != legal_description:
            question_title = question_text

    return AssessmentQuestionResponse(
        id=question.id,
        checklist_id=question.checklist_id,
        section_id=question.section_id,
        parent_question_id=question.parent_question_id,
        question_id=question.question_code,
        question_title=question_title,
        security_level=question.severity or SeverityLevel.low,
        audit_type=question.audit_type if question.audit_type else None,
        answer_logic=question.answer_logic,
        legal_requirement=legal_requirement,
        explanation=translation.explanation if translation and translation.explanation else "",
        expected_implementation=sanitize_html(translation.expected_implementation) if translation and translation.expected_implementation else "",
        how_it_works=translation.how_it_works if translation and translation.how_it_works else None,
        why_this_matters=translation.how_it_works if translation and translation.how_it_works else None,
        points=_severity_to_points(question.severity or SeverityLevel.low),
        report_domain=question.report_domain,
        report_chapter=question.report_chapter,
        illustrative_image_id=question.illustrative_image_id,
        note_enabled=question.note_enabled,
        evidence_enabled=question.evidence_enabled,
        customer_answer=customer_answer,
        customer_answer_status=customer_answer_status,
        admin_note=admin_note,
        user_note=user_note,
        evidence_rule=EvidenceRuleResponse(
            allowed_mime_types=["application/pdf", "image/png", "image/jpeg"],
            max_file_size_bytes=10 * 1024 * 1024,
        ),
        evidence_files=[
            {
                "id": str(evidence.id),
                "media_id": str(evidence.media_id),
                "filename": evidence.media.original_filename,
                "mime_type": evidence.media.mime_type,
                "file_size": evidence.media.file_size_bytes,
                "scan_status": evidence.media.scan_status,
                "encryption_status": evidence.media.encryption_status,
                "uploaded_at": evidence.uploaded_at.isoformat() if evidence.uploaded_at else None,
            }
            for evidence in evidence_files
        ],
        answer_options=_answer_options_for_assessment(question, translation),
        sub_questions=sub_questions,
    )


def _serialize_assessment_detail(
    db: Session, assessment: Assessment, lang_code: str | None = None
) -> AssessmentDetailResponse:
    checklist = db.get(Checklist, assessment.checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")

    resolved_lang = lang_code or DEFAULT_LANGUAGE_CODE
    checklist_translation = _checklist_translation_for_language(db, checklist.id, resolved_lang)
    checklist_title = checklist_translation.title if checklist_translation else f"Checklist v{checklist.version}"

    sections = db.scalars(
        select(ChecklistSection)
        .where(ChecklistSection.checklist_id == checklist.id)
        .order_by(ChecklistSection.display_order)
    ).all()

    questions = db.scalars(
        select(ChecklistQuestion)
        .options(selectinload(ChecklistQuestion.answer_options))
        .where(
            ChecklistQuestion.checklist_id == checklist.id,
            ChecklistQuestion.is_active.is_(True),
        )
        .order_by(ChecklistQuestion.display_order)
    ).all()

    answers = db.scalars(
        select(AssessmentAnswer).where(AssessmentAnswer.assessment_id == assessment.id)
    ).all()
    answer_map = {answer.question_id: answer for answer in answers}

    children_map: dict[UUID, list[ChecklistQuestion]] = {}
    for question in questions:
        if question.parent_question_id is not None:
            children_map.setdefault(question.parent_question_id, []).append(question)

    section_responses: list[AssessmentSectionResponse] = []
    for section in sections:
        section_translation = _section_translation_for_language(db, section.id, resolved_lang)
        section_responses.append(
            AssessmentSectionResponse(
                id=section.id,
                checklist_id=section.checklist_id,
                title=section_translation.title if section_translation else section.section_code,
                order=section.display_order,
                questions=[
                    _to_assessment_question_response(
                        question, answer_map, children_map, db, assessment, resolved_lang
                    )
                    for question in sorted(questions, key=lambda q: q.display_order)
                    if question.section_id == section.id and question.parent_question_id is None
                ],
            )
        )

    return AssessmentDetailResponse(
        assessment_id=assessment.id,
        checklist_id=assessment.checklist_id,
        user_id=assessment.user_id,
        access_window_id=assessment.access_window_id,
        company_id=assessment.company_id,
        status=assessment.status,
        started_at=assessment.started_at,
        expires_at=assessment.expires_at,
        completion_percent=float(assessment.completion_percent),
        is_new=False,
        checklist_title=checklist_title,
        sections=section_responses,
    )


def get_current_assessment_detail(db: Session, *, user: User, checklist_id: UUID | None = None, company_id: UUID | None = None, lang_code: str | None = None) -> AssessmentDetailResponse:
    assessment = _get_active_assessment(db, user=user, checklist_id=checklist_id, company_id=company_id)
    db.refresh(assessment)  # Ensure we have latest completion_percent
    return _serialize_assessment_detail(db, assessment, lang_code=lang_code)


def get_assessment_detail_by_id(
    db: Session,
    *,
    user: User,
    assessment_id: UUID,
    company_id: UUID | None = None,
    lang_code: str | None = None,
) -> AssessmentDetailResponse:
    """Return checklist detail for an owned assessment (including submitted, for read-only viewing)."""
    query = select(Assessment).where(Assessment.id == assessment_id, Assessment.user_id == user.id)
    if company_id is not None:
        query = query.where(Assessment.company_id == company_id)
    assessment = db.scalar(query)
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("assessment_not_found", lang_code or "en"),
        )

    # Privacy retention enforcement: once retention window elapses after report
    # publication (or purge has run), keep the record in history but block viewing.
    now = _now_utc()
    if assessment.purged_at is not None or (
        assessment.retention_expires_at is not None and assessment.retention_expires_at <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assessment details are no longer viewable due to privacy retention policy.",
        )

    return _serialize_assessment_detail(db, assessment, lang_code=lang_code)


def upsert_assessment_answer(
    db: Session,
    *,
    user: User,
    assessment_id: UUID,
    company_id: UUID | None = None,
    question_id: UUID,
    answer: AnswerChoice | int,
    note_text: str | None,
    lang_code: str = "en",
) -> AssessmentAnswerResponse:
    assessment = _get_owned_active_assessment(db, user=user, assessment_id=assessment_id, company_id=company_id, lang_code=lang_code)
    _question_for_assessment(db, assessment=assessment, question_id=question_id, lang_code=lang_code)

    existing = db.scalar(
        select(AssessmentAnswer).where(
            AssessmentAnswer.assessment_id == assessment.id,
            AssessmentAnswer.question_id == question_id,
        )
    )
    is_new_answer = existing is None

    # Convert integer to AnswerChoice if needed
    if isinstance(answer, int):
        answer_choice = AnswerChoice.from_id(answer)
        if answer_choice is None:
            raise HTTPException(status_code=400, detail=f"Invalid answer ID: {answer}")
    else:
        answer_choice = AnswerChoice(answer)

    if existing is None:
        existing = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=question_id,
            answer=answer_choice,
            answer_score=ANSWER_SCORES[answer_choice],
            weighted_priority=_priority_for_choice(answer_choice),
            note_text=note_text,
        )
        db.add(existing)
    else:
        existing.answer = answer_choice
        existing.answer_score = ANSWER_SCORES[answer_choice]
        existing.weighted_priority = _priority_for_choice(answer_choice)
        existing.note_text = note_text

    if assessment.status == AssessmentStatus.not_started:
        assessment.status = AssessmentStatus.in_progress
        assessment.started_at = assessment.started_at or _now_utc()

    completion = _recompute_completion(db, assessment=assessment)
    db.commit()
    db.refresh(assessment)  # Refresh assessment to get updated completion_percent
    db.refresh(existing)

    _log_assessment_audit(
        db,
        action="assessment_answer_create" if is_new_answer else "assessment_answer_update",
        assessment=assessment,
        actor_user_id=user.id,
        changes_summary=f"Answered question {question_id} in assessment {assessment_id}",
        after_data={"question_id": str(question_id), "answer": answer_choice.value},
    )

    return AssessmentAnswerResponse(
        assessment_id=assessment.id,
        question_id=question_id,
        answer=answer_choice,
        answer_score=existing.answer_score,
        weighted_priority=existing.weighted_priority,
        completion_percent=completion,
    )


def submit_assessment(db: Session, *, user: User, assessment_id: UUID, company_id: UUID | None = None, lang_code: str = "en") -> AssessmentSubmitResponse:
    assessment = _get_owned_active_assessment(db, user=user, assessment_id=assessment_id, company_id=company_id, lang_code=lang_code)
    completion = _recompute_completion(db, assessment=assessment)

    # Validation removed - users can submit assessment at any completion level
    # _validate_assessment_completion(db, assessment)

    assessment.status = AssessmentStatus.submitted
    assessment.submitted_at = _now_utc()

    # Create assessment review for admin review
    from app.models.assessment_review import AssessmentReview
    existing_review = db.scalar(
        select(AssessmentReview).where(AssessmentReview.assessment_id == assessment.id)
    )
    
    if not existing_review:
        review = AssessmentReview(
            assessment_id=assessment.id,
            status="pending",  # Use string instead of enum to avoid import issues
            completion_percentage=completion,
        )
        db.add(review)

    db.commit()
    db.refresh(assessment)

    _log_assessment_audit(
        db,
        action="assessment_submit",
        assessment=assessment,
        actor_user_id=user.id,
        changes_summary=f"Submitted assessment {assessment_id}",
        after_data={"status": str(assessment.status), "completion_percent": completion},
    )

    # Auto-generate draft report when assessment is submitted
    import logging
    logger = logging.getLogger(__name__)
    try:
        from app.services.report import generate_draft_report
        generate_draft_report(db, assessment_id=assessment_id, actor=user, lang_code=lang_code)
        logger.info(f"Draft report auto-generated for assessment {assessment_id}")
    except Exception as e:
        # Log error but don't fail the submission (frontend will create draft as fallback)
        logger.error(f"Failed to auto-generate report for assessment {assessment_id}: {e}", exc_info=True)

    # Send notification
    try:
        event = NotificationEvent(
            event_type=NotificationEventType.ASSESSMENT_SUBMITTED,
            user_id=user.id,
            assessment_id=assessment.id,
            lang_code=lang_code,
        )
        notification_service = NotificationService(db)
        notification_service.notify(event)
    except Exception as e:
        logger.error(f"Failed to send assessment_submitted notification: {e}", exc_info=True)

    return AssessmentSubmitResponse(
        assessment_id=assessment.id,
        status=assessment.status,
        submitted_at=assessment.submitted_at,
        completion_percent=completion,
    )


def _get_section_and_question_order(db: Session, checklist_id: UUID):
    """
    Returns a list of section IDs in order, and for each section, a list of question IDs in order.
    """
    from app.models.checklist import ChecklistSection, ChecklistQuestion

    sections = db.execute(
        select(ChecklistSection.id)
        .where(ChecklistSection.checklist_id == checklist_id)
        .order_by(ChecklistSection.display_order)
    ).scalars().all()
    section_questions = {}
    for section_id in sections:
        questions = db.execute(
            select(ChecklistQuestion.id, ChecklistQuestion.parent_question_id)
            .where(ChecklistQuestion.section_id == section_id)
            .order_by(ChecklistQuestion.display_order)
        ).all()
        section_questions[section_id] = questions
    return sections, section_questions


def _validate_assessment_completion(db: Session, assessment: Assessment):
    """
    Validation disabled - users can submit assessments at any completion level.
    This function is kept for backward compatibility but does not enforce any restrictions.
    """
    pass

