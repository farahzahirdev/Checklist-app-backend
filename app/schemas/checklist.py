from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

class ChecklistTypeInfo(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None

class ChecklistPricingInfo(BaseModel):
    price_id: str | None = None
    amount_cents: int | None = None
    currency: str | None = None

class CustomerChecklistResponse(BaseModel):
    id: UUID
    title: str
    checklist_type: ChecklistTypeInfo
    version: str
    status: str
    created_at: datetime
    updated_at: datetime
    pricing: ChecklistPricingInfo | None = None
