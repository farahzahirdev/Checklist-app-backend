from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaymentStatus(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    checklist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklists.id", ondelete="RESTRICT"),
        nullable=True,
    )
    stripe_payment_intent_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=PaymentStatus.pending.value)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="payments")
    access_windows = relationship("AccessWindow", back_populates="payment")
