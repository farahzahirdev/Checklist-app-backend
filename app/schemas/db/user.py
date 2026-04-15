from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password_hash: str
    role: str = Field(default=UserRole.customer, description="Role code: admin, auditor, or customer")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: str = Field(description="Role code: admin, auditor, or customer")
    is_active: bool
    created_at: datetime
    updated_at: datetime
