from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccessEventType(StrEnum):
    unlocked_after_payment = "unlocked_after_payment"
    assessment_started = "assessment_started"
    access_expired = "access_expired"
    manually_extended = "manually_extended"
    manually_revoked = "manually_revoked"


class AccessEvent(Base):
    __tablename__ = "access_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    access_window_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("access_windows.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[AccessEventType] = mapped_column(
        Enum(AccessEventType, name="access_event_type", native_enum=True), nullable=False
    )
    event_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
