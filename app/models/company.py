"""
Company/Organization Models

Models for managing companies, organizations, and user affiliations within companies.
Supports multi-company audit scenarios where users have different roles in different companies.
"""
from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanySize(StrEnum):
    """Company size classifications."""
    startup = "startup"           # < 50 employees
    small = "small"               # 50-250 employees
    medium = "medium"             # 250-1000 employees
    large = "large"               # 1000-5000 employees
    enterprise = "enterprise"     # > 5000 employees


class CompanyIndustry(StrEnum):
    """Industry classifications for contextualized audits."""
    healthcare = "healthcare"
    finance = "finance"
    technology = "technology"
    manufacturing = "manufacturing"
    retail = "retail"
    energy = "energy"
    education = "education"
    government = "government"
    other = "other"


class UserCompanyRole(StrEnum):
    """User's role within a company."""
    owner = "owner"               # Company owner/founder
    manager = "manager"           # Manager/team lead
    executive = "executive"       # C-level or director
    lead = "lead"                 # Team lead/supervisor
    staff = "staff"               # Regular staff
    auditor = "auditor"           # Internal auditor/compliance
    other = "other"


class Company(Base):
    """
    Represents a company/organization in the audit system.
    
    Companies can be associated with multiple users, who may have different roles.
    This enables audit systems where the same person audits for different organizations.
    """
    
    __tablename__ = "companies"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Basic identity
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Contact and location
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g., "EU", "US", "APAC"
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Business context
    industry: Mapped[str | None] = mapped_column(String(50), nullable=True)  # CompanyIndustry
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)  # CompanySize
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Compliance context
    compliance_framework: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g., ISO 27001, HIPAA, SOC 2, GDPR"
    )
    
    # Status and metadata
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Relationships
    user_assignments: Mapped[list["UserCompanyAssignment"]] = relationship(
        "UserCompanyAssignment",
        back_populates="company",
        cascade="all, delete-orphan",
        foreign_keys="UserCompanyAssignment.company_id"
    )
    
    def __str__(self) -> str:
        return f"{self.name} ({self.slug})"


class UserCompanyAssignment(Base):
    """
    Maps users to companies with their specific role within that company.
    
    Enables scenarios where:
    - A user audits for multiple companies
    - A user has different roles in different companies
    - A company has multiple users with different roles
    
    Example:
    - John is "auditor" for CompanyA and "manager" for CompanyB
    - CompanyA has John (auditor), Jane (owner), and Mike (staff)
    """
    
    __tablename__ = "user_company_assignments"
    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_user_company"),)
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # Foreign keys
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # User's role within this company
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="User's role in this company (owner, manager, staff, auditor, etc.)"
    )
    
    # Job title (optional, more specific than role)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Department or team (optional)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    
    # Timestamps
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="company_assignments",
        foreign_keys=[user_id]
    )
    company: Mapped[Company] = relationship(
        "Company",
        back_populates="user_assignments",
        foreign_keys=[company_id]
    )
    
    def __str__(self) -> str:
        return f"{self.user.email} ({self.role}) @ {self.company.name}"
