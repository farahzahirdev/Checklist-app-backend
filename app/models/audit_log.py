from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import UserRole


class AuditAction(StrEnum):
    auth_login = "auth_login"
    auth_logout = "auth_logout"
    auth_mfa_verify = "auth_mfa_verify"
    checklist_create = "checklist_create"
    checklist_update = "checklist_update"
    checklist_publish = "checklist_publish"
    assessment_submit = "assessment_submit"
    report_approve = "report_approve"
    report_publish = "report_publish"
    user_role_change = "user_role_change"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    actor_role: Mapped[UserRole | None] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=True, create_constraint=False), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action", native_enum=True), nullable=False
    )
    target_entity: Mapped[str] = mapped_column(String(120), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
