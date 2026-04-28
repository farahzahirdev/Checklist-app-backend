from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_window import AccessWindow
from app.models.assessment import AnswerChoice, Assessment, AssessmentAnswer, AssessmentStatus, PriorityLevel
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
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssessmentAnswerResponse,
    AssessmentDetailResponse,
    AssessmentQuestionResponse,
    AssessmentSectionResponse,
    AssessmentSessionResponse,
    AssessmentSubmitResponse,
)
from app.utils.i18n_messages import translate
from app.schemas.admin_checklist import EvidenceRuleResponse


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_assessment(assessment: Assessment, *, is_new: bool) -> AssessmentSessionResponse:
    return AssessmentSessionResponse(
        assessment_id=assessment.id,
        checklist_id=assessment.checklist_id,
        user_id=assessment.user_id,
        access_window_id=assessment.access_window_id,
        status=assessment.status,
        started_at=assessment.started_at,
        expires_at=assessment.expires_at,
        completion_percent=float(assessment.completion_percent),
        is_new=is_new,
    )


def _latest_succeeded_payment(db: Session, *, user_id: UUID, checklist_id: UUID) -> Payment | None:
    return db.scalar(
        select(Payment)
        .where(
            Payment.user_id == user_id,
            Payment.checklist_id == checklist_id,
            Payment.status == PaymentStatus.succeeded,
        )
        .order_by(desc(Payment.paid_at), desc(Payment.created_at))
    )


def _active_access_window(db: Session, *, user_id: UUID, now: datetime) -> AccessWindow | None:
    return db.scalar(
        select(AccessWindow)
        .where(AccessWindow.user_id == user_id, AccessWindow.expires_at > now)
        .order_by(desc(AccessWindow.expires_at))
    )


def _ensure_access_window(db: Session, *, user: User, payment: Payment | None, now: datetime) -> AccessWindow:
    settings = get_settings()
    existing = _active_access_window(db, user_id=user.id, now=now)
    if existing is not None:
        return existing

    access_window = AccessWindow(
        user_id=user.id,
        payment_id=payment.id if payment else None,
        activated_at=now,
        expires_at=now + timedelta(days=settings.access_unlock_days),
    )
    db.add(access_window)
    db.flush()
    return access_window


def _get_active_assessment(
    db: Session, *, user: User, checklist_id: UUID | None = None, lang_code: str = "en"
) -> Assessment:
    now = _now_utc()
    conditions = [Assessment.user_id == user.id, Assessment.expires_at > now]
    if checklist_id is not None:
        conditions.append(Assessment.checklist_id == checklist_id)
    assessment = db.scalar(
        select(Assessment)
        .where(*conditions)
        .where(Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]))
        .order_by(desc(Assessment.created_at))
    )
    if assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("assessment_not_found", lang_code))
    return assessment


def get_current_assessment(db: Session, *, user: User, checklist_id: UUID | None = None, lang_code: str | None = None) -> AssessmentSessionResponse:
    assessment = _get_active_assessment(db, user=user, checklist_id=checklist_id)
    return _serialize_assessment(assessment, is_new=False)


def start_assessment(
    db: Session, *, user: User, checklist_id: UUID, lang_code: str = "en"
) -> AssessmentSessionResponse:
    now = _now_utc()
    checklist = db.get(Checklist, checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("checklist_not_found", lang_code))
    if checklist.status != ChecklistStatus.published:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate("checklist_not_published", lang_code))
    existing = db.scalar(
        select(Assessment)
        .where(
            Assessment.user_id == user.id,
            Assessment.checklist_id == checklist_id,
            Assessment.expires_at > now,
            Assessment.status.in_([AssessmentStatus.not_started, AssessmentStatus.in_progress]),
        )
        .order_by(desc(Assessment.created_at))
    )
    if existing is not None:
        return _serialize_assessment(existing, is_new=False)
    if user.role == UserRole.admin:
        access_window = _ensure_access_window(db, user=user, payment=None, now=now)
    else:
        payment = _latest_succeeded_payment(db, user_id=user.id, checklist_id=checklist_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=translate("payment_required", lang_code))
        access_window = _ensure_access_window(db, user=user, payment=payment, now=now)
    settings = get_settings()
    assessment = Assessment(
        user_id=user.id,
        checklist_id=checklist_id,
        access_window_id=access_window.id,
        started_at=now,
        status=AssessmentStatus.in_progress,
        expires_at=now + timedelta(days=settings.assessment_completion_days),
        completion_percent=0,
    )
    db.add(assessment)
    db.flush()
    db.commit()
    db.refresh(assessment)
    return _serialize_assessment(assessment, is_new=True)


ANSWER_SCORES: dict[AnswerChoice, int] = {
    AnswerChoice.four: 4,
    AnswerChoice.three: 3,
    AnswerChoice.two: 2,
    AnswerChoice.one: 1,
}


def _get_owned_active_assessment(
    db: Session, *, user: User, assessment_id: UUID, lang_code: str = "en"
) -> Assessment:
    assessment = db.scalar(select(Assessment).where(Assessment.id == assessment_id, Assessment.user_id == user.id))
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


def _to_assessment_question_response(
    question: ChecklistQuestion,
    answer_map: dict[UUID, AssessmentAnswer],
    children_map: dict[UUID, list[ChecklistQuestion]],
    db: Session,
) -> 'AssessmentQuestionResponse':
    translation = _latest_question_translation(db, question.id)
    customer_answer = None
    customer_answer_status = "not_started"
    answer = answer_map.get(question.id)
    if answer is not None and answer.answer is not None:
        customer_answer = answer.answer
        customer_answer_status = "answered"

    sub_questions = [
        _to_assessment_question_response(subq, answer_map, children_map, db)
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

    return AssessmentQuestionResponse(
        id=question.id,
        checklist_id=question.checklist_id,
        section_id=question.section_id,
        parent_question_id=question.parent_question_id,
        question_id=question.question_code,
        question_title=translation.paragraph_title if translation else None,
        security_level=question.severity or SeverityLevel.low,
        audit_type=question.audit_type,
        answer_logic=question.answer_logic,
        legal_requirement=translation.question_text if translation else "",
        explanation=translation.explanation if translation and translation.explanation else "",
        expected_implementation=translation.expected_implementation if translation and translation.expected_implementation else "",
        how_it_works=translation.how_it_works if translation and translation.how_it_works else None,
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
        sub_questions=sub_questions,
    )


def _serialize_assessment_detail(db: Session, assessment: Assessment) -> AssessmentDetailResponse:
    checklist = db.get(Checklist, assessment.checklist_id)
    if checklist is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="checklist_not_found")

    checklist_translation = _latest_checklist_translation(db, checklist.id)
    checklist_title = checklist_translation.title if checklist_translation else f"Checklist v{checklist.version}"

    sections = db.scalars(
        select(ChecklistSection)
        .where(ChecklistSection.checklist_id == checklist.id)
        .order_by(ChecklistSection.display_order)
    ).all()

    questions = db.scalars(
        select(ChecklistQuestion)
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
        title = _latest_section_translation(db, section.id)
        section_responses.append(
            AssessmentSectionResponse(
                id=section.id,
                checklist_id=section.checklist_id,
                title=title.title if title else section.section_code,
                order=section.display_order,
                questions=[
                    _to_assessment_question_response(question, answer_map, children_map, db)
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
        status=assessment.status,
        started_at=assessment.started_at,
        expires_at=assessment.expires_at,
        completion_percent=float(assessment.completion_percent),
        is_new=False,
        checklist_title=checklist_title,
        sections=section_responses,
    )


def get_current_assessment_detail(db: Session, *, user: User, checklist_id: UUID | None = None, lang_code: str | None = None) -> AssessmentDetailResponse:
    assessment = _get_active_assessment(db, user=user, checklist_id=checklist_id)
    db.refresh(assessment)  # Ensure we have latest completion_percent
    return _serialize_assessment_detail(db, assessment)


def upsert_assessment_answer(
    db: Session,
    *,
    user: User,
    assessment_id: UUID,
    question_id: UUID,
    answer: AnswerChoice | int,
    note_text: str | None,
    lang_code: str = "en",
) -> AssessmentAnswerResponse:
    assessment = _get_owned_active_assessment(db, user=user, assessment_id=assessment_id, lang_code=lang_code)
    _question_for_assessment(db, assessment=assessment, question_id=question_id, lang_code=lang_code)

    existing = db.scalar(
        select(AssessmentAnswer).where(
            AssessmentAnswer.assessment_id == assessment.id,
            AssessmentAnswer.question_id == question_id,
        )
    )

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

    return AssessmentAnswerResponse(
        assessment_id=assessment.id,
        question_id=question_id,
        answer=answer_choice,
        answer_score=existing.answer_score,
        weighted_priority=existing.weighted_priority,
        completion_percent=completion,
    )


def submit_assessment(db: Session, *, user: User, assessment_id: UUID, lang_code: str = "en") -> AssessmentSubmitResponse:
    assessment = _get_owned_active_assessment(db, user=user, assessment_id=assessment_id, lang_code=lang_code)
    completion = _recompute_completion(db, assessment=assessment)

    # Validation removed - users can submit assessment at any completion level
    # _validate_assessment_completion(db, assessment)

    assessment.status = AssessmentStatus.submitted
    assessment.submitted_at = _now_utc()

    db.commit()
    db.refresh(assessment)

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


def _ensure_access_window(db: Session, *, user: User, payment: Payment | None, now: datetime) -> AccessWindow:
    settings = get_settings()
    existing = _active_access_window(db, user_id=user.id, now=now)
    if existing is not None:
        return existing

    access_window = AccessWindow(
        user_id=user.id,
        payment_id=payment.id if payment else None,
        activated_at=now,
        expires_at=now + timedelta(days=settings.access_unlock_days),
    )
    db.add(access_window)
    db.flush()
    return access_window
