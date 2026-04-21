from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.access_window import AccessWindow
from app.models.assessment import AnswerChoice, Assessment, AssessmentAnswer, AssessmentStatus, PriorityLevel
from app.models.checklist import Checklist, ChecklistQuestion, ChecklistStatus
from app.models.payment import Payment, PaymentStatus
from app.models.user import User, UserRole
from app.schemas.assessment import (
    AssessmentAnswerResponse,
    AssessmentSessionResponse,
    AssessmentSubmitResponse,
)
from app.utils.i18n_messages import translate

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


def get_current_assessment(
    db: Session, *, user: User, checklist_id: UUID | None = None, lang_code: str = "en"
) -> AssessmentSessionResponse:
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
    AnswerChoice.yes: 4,
    AnswerChoice.partially: 3,
    AnswerChoice.dont_know: 2,
    AnswerChoice.no: 1,
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
    if choice == AnswerChoice.no:
        return PriorityLevel.high
    if choice == AnswerChoice.dont_know:
        return PriorityLevel.medium
    return PriorityLevel.low


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


def upsert_assessment_answer(
    db: Session,
    *,
    user: User,
    assessment_id: UUID,
    question_id: UUID,
    answer: AnswerChoice,
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

    if existing is None:
        existing = AssessmentAnswer(
            assessment_id=assessment.id,
            question_id=question_id,
            answer=answer,
            answer_score=ANSWER_SCORES[answer],
            weighted_priority=_priority_for_choice(answer),
            note_text=note_text,
        )
        db.add(existing)
    else:
        existing.answer = answer
        existing.answer_score = ANSWER_SCORES[answer]
        existing.weighted_priority = _priority_for_choice(answer)
        existing.note_text = note_text

    if assessment.status == AssessmentStatus.not_started:
        assessment.status = AssessmentStatus.in_progress
        assessment.started_at = assessment.started_at or _now_utc()

    completion = _recompute_completion(db, assessment=assessment)
    db.commit()
    db.refresh(existing)

    return AssessmentAnswerResponse(
        assessment_id=assessment.id,
        question_id=question_id,
        answer=existing.answer,
        answer_score=existing.answer_score,
        weighted_priority=existing.weighted_priority,
        completion_percent=completion,
    )


def submit_assessment(db: Session, *, user: User, assessment_id: UUID, lang_code: str = "en") -> AssessmentSubmitResponse:
    assessment = _get_owned_active_assessment(db, user=user, assessment_id=assessment_id, lang_code=lang_code)
    completion = _recompute_completion(db, assessment=assessment)

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
