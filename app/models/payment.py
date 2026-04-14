from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaymentStatus(StrEnum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"

    @classmethod
    def to_id(cls, status: "PaymentStatus | str") -> int:
        value = cls(status)
        mapping = {cls.pending: 1, cls.succeeded: 2, cls.failed: 3}
        return mapping[value]

    @classmethod
    def from_id(cls, status_code_id: int | None) -> "PaymentStatus | None":
        mapping = {1: cls.pending, 2: cls.succeeded, 3: cls.failed}
        return mapping.get(status_code_id)


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
    status_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("payment_status_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @property
    def status(self) -> PaymentStatus | None:
        return PaymentStatus.from_id(self.status_code_id)

    @status.setter
    def status(self, value: PaymentStatus | str | None) -> None:
        self.status_code_id = None if value is None else PaymentStatus.to_id(value)

    user = relationship("User", back_populates="payments")
    access_windows = relationship("AccessWindow", back_populates="payment")
