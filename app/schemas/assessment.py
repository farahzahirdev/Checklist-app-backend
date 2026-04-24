from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.models.assessment import AnswerChoice, AssessmentStatus, PriorityLevel
from app.models.checklist import SeverityLevel
from app.schemas.admin_checklist import EvidenceRuleResponse


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


class AssessmentQuestionResponse(BaseModel):
    id: UUID
    checklist_id: UUID
    section_id: UUID
    parent_question_id: UUID | None = None
    question_id: str
    security_level: SeverityLevel
    audit_type: str = "compliance"
    answer_logic: str = "answer_only"
    legal_requirement: str
    explanation: str
    expected_implementation: str
    points: int
    report_domain: str | None = None
    report_chapter: str | None = None
    illustrative_image_id: UUID | None = None
    note_enabled: bool = True
    evidence_enabled: bool = True
    customer_answer: AnswerChoice | None = None
    customer_answer_status: Literal["not_started", "answered"] = "not_started"
    note: str | None = None
    evidence_rule: EvidenceRuleResponse
    sub_questions: list[AssessmentQuestionResponse] = []


class AssessmentSectionResponse(BaseModel):
    id: UUID
    checklist_id: UUID
    title: str
    order: int
    questions: list[AssessmentQuestionResponse] = []


class AssessmentDetailResponse(BaseModel):
    assessment_id: UUID
    checklist_id: UUID
    user_id: UUID
    access_window_id: UUID
    status: AssessmentStatus
    started_at: datetime | None
    expires_at: datetime
    completion_percent: float
    is_new: bool = False
    checklist_title: str
    sections: list[AssessmentSectionResponse] = []
