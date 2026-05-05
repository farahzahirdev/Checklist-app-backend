from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(StrEnum):
    admin = "admin"
    auditor = "auditor"
    customer = "customer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Core identity
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Optional: Display name/username
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True, index=True)
    
    # Role in system (admin/auditor/customer)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=UserRole.customer.value)
    
    # Optional: Company/Organization context (for audit multi-company scenario)
    # This is the user's "primary" company for quick reference
    # Full company associations are tracked in UserCompanyAssignment table
    primary_company_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36),  # Store as string for flexibility, reference UUID
        nullable=True,
        comment="User's primary company (for quick reference, full list in user_company_assignments)"
    )
    
    # Optional: User's job title at their primary company
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Optional: Department at primary company
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Status
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
    user_roles_rel = relationship("UserRoleAssignment", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserRoleAssignment.user_id")
    password_reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan", foreign_keys="PasswordResetToken.user_id")
    issued_password_reset_tokens = relationship("PasswordResetToken", back_populates="issued_by_user", foreign_keys="PasswordResetToken.issued_by_user_id")
    support_tickets = relationship("SupportTicket", back_populates="customer", cascade="all, delete-orphan", foreign_keys="SupportTicket.customer_id")
    support_ticket_messages = relationship("SupportTicketMessage", back_populates="sender", cascade="all, delete-orphan", foreign_keys="SupportTicketMessage.sender_user_id")
    
    # Company associations (multi-company support for audits)
    company_assignments = relationship("UserCompanyAssignment", back_populates="user", cascade="all, delete-orphan", foreign_keys="UserCompanyAssignment.user_id")

    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
