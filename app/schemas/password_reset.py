from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AdminPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8)
    reason: str | None = Field(default=None, max_length=500)


class AdminPasswordResetResponse(BaseModel):
    user_id: UUID
    email: str
    message: str
    reset_at: datetime
    reset_by_user_id: UUID
