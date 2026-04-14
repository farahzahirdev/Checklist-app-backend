from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.assessment import AnswerChoice, AssessmentStatus, PriorityLevel


class StartAssessmentRequest(BaseModel):
    checklist_id: UUID


class AssessmentSessionResponse(BaseModel):
    assessment_id: UUID
    checklist_id: UUID
    user_id: UUID
    access_window_id: UUID
    status: AssessmentStatus
    started_at: datetime | None
    expires_at: datetime
    completion_percent: float
    is_new: bool = False


class AssessmentAnswerUpsertRequest(BaseModel):
    question_id: UUID
    answer: AnswerChoice
    note_text: str | None = None


class AssessmentAnswerResponse(BaseModel):
    assessment_id: UUID
    question_id: UUID
    answer: AnswerChoice
    answer_score: int
    weighted_priority: PriorityLevel | None
    completion_percent: float


class AssessmentSubmitResponse(BaseModel):
    assessment_id: UUID
    status: AssessmentStatus
    submitted_at: datetime
    completion_percent: float
