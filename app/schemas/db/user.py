from datetime import datetime
from enum import IntEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRoleCode(IntEnum):
    admin = 0
    auditor = 1
    customer = 2


class UserCreate(BaseModel):
    email: EmailStr
    password_hash: str
    role: UserRoleCode = Field(default=UserRoleCode.customer, description="Role code: 0 admin, 1 auditor, 2 customer")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    role: UserRoleCode = Field(description="Role code: 0 admin, 1 auditor, 2 customer")
    is_active: bool
    created_at: datetime
    updated_at: datetime
