from enum import StrEnum

from pydantic import BaseModel


class UserRole(StrEnum):
    admin = "admin"
    auditor = "auditor"
    customer = "customer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RoleAssignment(BaseModel):
    role: UserRole