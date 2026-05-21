from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SystemSettingResponse(BaseModel):
    id: UUID
    key: str
    value: str
    value_type: str
    category: str
    description: str | None = None
    is_secret: bool
    has_value: bool = False
    is_locked: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemSettingUpdateRequest(BaseModel):
    value: str = Field(default="")
    reason: str | None = None


class SystemSettingListResponse(BaseModel):
    total: int
    categories: list[str]
    settings: list[SystemSettingResponse]
