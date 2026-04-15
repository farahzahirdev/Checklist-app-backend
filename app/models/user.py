from datetime import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_code_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("role_codes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    access_windows = relationship("AccessWindow", back_populates="user", cascade="all, delete-orphan")
    mfa_totp = relationship("MfaTotp", back_populates="user", cascade="all, delete-orphan", uselist=False)
