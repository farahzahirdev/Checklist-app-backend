"""
Role-Based Access Control (RBAC) Models

Defines permissions, roles, and their associations for granular access control.
"""
from datetime import datetime
from enum import StrEnum
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Table, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PermissionResource(StrEnum):
    """Core resources that can be protected by permissions."""
    
    # Checklist resources
    checklist = "checklist"
    checklist_admin = "checklist_admin"
    
    # Assessment resources
    assessment = "assessment"
    assessment_submit = "assessment_submit"
    
    # Dashboard & reporting
    dashboard = "dashboard"
    report = "report"
    
    # User & admin resources
    user_management = "user_management"
    payment_management = "payment_management"
    permission_management = "permission_management"
    audit_log = "audit_log"


class PermissionAction(StrEnum):
    """Actions that can be performed on resources."""
    
    create = "create"
    read = "read"
    update = "update"
    delete = "delete"
    submit = "submit"
    manage = "manage"


class Permission(Base):
    """
    Represents a specific permission in the system.
    
    Permissions are granular and follow the pattern: resource:action
    Example: "checklist:read", "assessment:submit", "user_management:manage"
    """
    
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),)
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource: Mapped[str] = mapped_column(String(50), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="permission",
        cascade="all, delete-orphan",
        foreign_keys="RolePermission.permission_id"
    )
    
    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"


class Role(Base):
    """
    Represents a role in the RBAC system.
    
    Roles are collections of permissions. Three predefined roles exist:
    - admin: Full system access
    - auditor: Read-only access to data
    - customer: Limited access to own assessments and dashboards
    """
    
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("code", name="uq_roles_code"),)
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # admin, auditor, customer
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_system_role: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Relationships
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        "RolePermission",
        back_populates="role",
        cascade="all, delete-orphan",
        foreign_keys="RolePermission.role_id"
    )
    user_roles: Mapped[list["UserRoleAssignment"]] = relationship(
        "UserRoleAssignment",
        back_populates="role",
        cascade="all, delete-orphan",
        foreign_keys="UserRoleAssignment.role_id"
    )
    
    def __str__(self) -> str:
        return f"{self.code} ({self.name})"


class RolePermission(Base):
    """
    Join table mapping roles to permissions.
    
    Associates permissions with roles in a many-to-many relationship.
    """
    
    __tablename__ = "role_permissions"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),)
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    role: Mapped[Role] = relationship(
        "Role",
        back_populates="role_permissions",
        foreign_keys=[role_id]
    )
    permission: Mapped[Permission] = relationship(
        "Permission",
        back_populates="role_permissions",
        foreign_keys=[permission_id]
    )


class UserRoleAssignment(Base):
    """
    Join table mapping users to roles.
    
    Associates roles with users in a many-to-many relationship.
    Allows a user to have multiple roles and enables flexible role assignment.
    """
    
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles"),)
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    assigned_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="user_roles_rel",
        foreign_keys=[user_id]
    )
    role: Mapped[Role] = relationship(
        "Role",
        back_populates="user_roles",
        foreign_keys=[role_id]
    )
    assigned_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[assigned_by]
    )
