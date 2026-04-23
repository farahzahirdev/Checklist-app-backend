from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class ChecklistTypeInfo(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None

class CustomerChecklistResponse(BaseModel):
    id: UUID
    title: str
    checklist_type: ChecklistTypeInfo
    version: str
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerChecklistListResponse(BaseModel):
    total: int
    checklists: list[CustomerChecklistResponse]
    skip: int
    limit: int
