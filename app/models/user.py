from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(StrEnum):
    """User role codes - references role_codes table. Not a database enum column."""
    admin = "admin"
    auditor = "auditor"
    customer = "customer"

    @classmethod
    def to_id(cls, role: "UserRole | str") -> int:
        value = cls(role)
        mapping = {cls.admin: 1, cls.auditor: 2, cls.customer: 3}
        return mapping[value]

    @classmethod
    def from_id(cls, role_code_id: int | None) -> "UserRole | None":
        mapping = {1: cls.admin, 2: cls.auditor, 3: cls.customer}
        return mapping.get(role_code_id)


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

    @property
    def role(self) -> UserRole | None:
        return UserRole.from_id(self.role_code_id)

    @role.setter
    def role(self, value: UserRole | str | None) -> None:
        self.role_code_id = None if value is None else UserRole.to_id(value)

    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")
    access_windows = relationship("AccessWindow", back_populates="user", cascade="all, delete-orphan")
    mfa_totp = relationship("MfaTotp", back_populates="user", cascade="all, delete-orphan", uselist=False)
