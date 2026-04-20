from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.checklist import ChecklistStatus, SeverityLevel


AuditType = Literal["compliance"]


class AdminChecklistCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    law_decree: str = Field(min_length=1, max_length=255)
    version: int = Field(default=1, ge=1)
    status: ChecklistStatus = ChecklistStatus.draft
    checklist_type_code: str = Field(default="compliance", min_length=1, max_length=80, description="Checklist type code (default: compliance)")


class AdminChecklistUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    law_decree: str | None = Field(default=None, min_length=1, max_length=255)
    version: int | None = Field(default=None, ge=1)
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


class AdminQuestionCreateRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    parent_question_id: UUID | None = None
    note: str | None = None
    security_level: SeverityLevel
    legal_requirement: str = Field(min_length=1)
    explanation: str = Field(default="")
    expected_implementation: str = Field(default="")


class AdminQuestionUpdateRequest(BaseModel):
    question_id: str | None = Field(default=None, min_length=1, max_length=120)
    parent_question_id: UUID | None = None
    note: str | None = None
    security_level: SeverityLevel | None = None
    legal_requirement: str | None = Field(default=None, min_length=1)
    explanation: str | None = None
    expected_implementation: str | None = None
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
    security_level: SeverityLevel
    audit_type: AuditType = "compliance"
    legal_requirement: str
    explanation: str
    expected_implementation: str
    points: int
    customer_answer: str | None = None
    customer_answer_status: Literal["not_started"] = "not_started"
    note: str | None = None
    evidence_rule: EvidenceRuleResponse
