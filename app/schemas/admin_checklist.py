from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.checklist import ChecklistStatus, SeverityLevel


AuditType = Literal["compliance"]
AnswerLogic = Literal["answer_only", "answer_with_adjustment"]


class AdminChecklistCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    law_decree: str = Field(min_length=1, max_length=255)
    status: ChecklistStatus = ChecklistStatus.draft
    checklist_type_code: str = Field(default="compliance", min_length=1, max_length=80, description="Checklist type code (default: compliance)")


class AdminChecklistUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    law_decree: str | None = Field(default=None, min_length=1, max_length=255)
    status: ChecklistStatus | None = None


class PublishChecklistRequest(BaseModel):
    status: ChecklistStatus = ChecklistStatus.published


class AdminChecklistResponse(BaseModel):
    id: UUID
    title: str
    audit_type: AuditType = "compliance"
    law_decree: str
    version: str
    status: ChecklistStatus
    created_at: datetime
    updated_at: datetime


class AdminSectionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    order: int = Field(ge=1)


class AdminSectionUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    order: int | None = Field(default=None, ge=1)


class AdminSectionResponse(BaseModel):
    id: UUID
    checklist_id: UUID
    title: str
    order: int


class AdminQuestionAnswerOptionRequest(BaseModel):
    position: int = Field(ge=1, le=4)
    label: str = Field(min_length=1, max_length=255)
    score: int = Field(ge=1, le=4)
    choice_code: str | None = Field(default=None, max_length=40)
    description: str | None = None
    illustrative_image_id: UUID | None = Field(default=None, description="Media ID for illustrative image")


class AdminQuestionAnswerOptionResponse(BaseModel):
    position: int
    label: str
    score: int
    choice_code: str | None = None
    description: str | None = None
    illustrative_image_id: UUID | None = None


class AdminQuestionCreateRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    question_title: str | None = Field(default=None, min_length=1)
    parent_question_id: UUID | None = None
    note: str | None = None
    security_level: SeverityLevel
    points: int | None = Field(default=None, ge=1, le=4)
    answer_logic: AnswerLogic = "answer_only"
    legal_requirement: str = Field(min_length=1)
    explanation: str = Field(default="")
    expected_implementation: str = Field(default="")
    guidance_score_4: str | None = None
    guidance_score_3: str | None = None
    guidance_score_2: str | None = None
    guidance_score_1: str | None = None
    recommendation_template: str | None = None
    illustrative_image_id: UUID | None = Field(default=None, description="Media ID for question illustrative image")
    answer_options: list[AdminQuestionAnswerOptionRequest] = Field(min_length=4, max_length=4, description="Exactly 4 answer options required")


class AdminQuestionUpdateRequest(BaseModel):
    question_id: str | None = Field(default=None, min_length=1, max_length=120)
    question_title: str | None = Field(default=None, min_length=1)
    parent_question_id: UUID | None = None
    note: str | None = None
    security_level: SeverityLevel | None = None
    points: int | None = Field(default=None, ge=1, le=4)
    answer_logic: AnswerLogic | None = None
    legal_requirement: str | None = Field(default=None, min_length=1)
    explanation: str | None = None
    expected_implementation: str | None = None
    guidance_score_4: str | None = None
    guidance_score_3: str | None = None
    guidance_score_2: str | None = None
    guidance_score_1: str | None = None
    recommendation_template: str | None = None
    illustrative_image_id: UUID | None = Field(default=None, description="Media ID for question illustrative image")
    answer_options: list[AdminQuestionAnswerOptionRequest] | None = None
    order: int | None = Field(default=None, ge=1)


class EvidenceRuleResponse(BaseModel):
    allowed_mime_types: list[str]
    max_file_size_bytes: int


class AdminQuestionResponse(BaseModel):
    id: UUID
    checklist_id: UUID
    section_id: UUID
    parent_question_id: UUID | None = None
    question_id: str
    question_title: str | None = None
    security_level: SeverityLevel
    audit_type: AuditType = "compliance"
    points: int
    answer_logic: AnswerLogic = "answer_only"
    legal_requirement: str
    explanation: str
    expected_implementation: str
    guidance_score_4: str | None = None
    guidance_score_3: str | None = None
    guidance_score_2: str | None = None
    guidance_score_1: str | None = None
    recommendation_template: str | None = None
    illustrative_image_id: UUID | None = None
    answer_options: list[AdminQuestionAnswerOptionResponse] = Field(default_factory=list)
    customer_answer: str | None = None
    customer_answer_status: Literal["not_started"] = "not_started"
    note: str | None = None
    evidence_rule: EvidenceRuleResponse
    sub_questions: list['AdminQuestionResponse'] = Field(default_factory=list)  # Recursive nesting
