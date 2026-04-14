from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.schemas.assessment import (
    AssessmentAnswerResponse,
    AssessmentAnswerUpsertRequest,
    AssessmentSessionResponse,
    AssessmentSubmitResponse,
    StartAssessmentRequest,
)
from app.services.assessment import get_current_assessment, start_assessment, submit_assessment, upsert_assessment_answer

router = APIRouter(prefix="/assessment", tags=["assessment"])


@router.post(
    "/start",
    response_model=AssessmentSessionResponse,
    summary="Start Assessment Session",
    description=(
        "Starts or resumes an in-progress assessment for the authenticated user. "
        "Requires a paid access window for the requested checklist."
    ),
)
def start_assessment_route(
    request: StartAssessmentRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSessionResponse:
    return start_assessment(db, user=current_user, checklist_id=request.checklist_id)


@router.get(
    "/current",
    response_model=AssessmentSessionResponse,
    summary="Get Current Assessment",
    description=(
        "Returns the active in-progress assessment for the current user. "
        "Optional checklist_id can narrow the lookup to a specific checklist."
    ),
)
def get_current_assessment_route(
    checklist_id: UUID | None = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSessionResponse:
    return get_current_assessment(db, user=current_user, checklist_id=checklist_id)


@router.put(
    "/{assessment_id}/answers",
    response_model=AssessmentAnswerResponse,
    summary="Save Assessment Answer",
    description=(
        "Creates or updates an answer for a question in an assessment. "
        "This endpoint is idempotent per assessment_id + question_id."
    ),
)
def upsert_answer_route(
    assessment_id: UUID,
    request: AssessmentAnswerUpsertRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentAnswerResponse:
    return upsert_assessment_answer(
        db,
        user=current_user,
        assessment_id=assessment_id,
        question_id=request.question_id,
        answer=request.answer,
        note_text=request.note_text,
    )


@router.post(
    "/{assessment_id}/submit",
    response_model=AssessmentSubmitResponse,
    summary="Submit Assessment",
    description=(
        "Finalizes an in-progress assessment, sets submitted timestamps, and locks the session for report generation."
    ),
)
def submit_assessment_route(
    assessment_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentSubmitResponse:
    return submit_assessment(db, user=current_user, assessment_id=assessment_id)
