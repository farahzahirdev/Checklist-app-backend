from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccessWindowCreate(BaseModel):
    user_id: UUID
    payment_id: UUID | None = None
    activated_at: datetime
    expires_at: datetime


class AccessWindowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    payment_id: UUID | None
    checklist_id: UUID | None
    activated_at: datetime
    expires_at: datetime
    created_at: datetime
