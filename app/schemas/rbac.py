"""
RBAC Schemas

Pydantic models for RBAC-related API requests and responses.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Permission Schemas
class PermissionResponse(BaseModel):
    """Response model for a permission."""
    
    id: UUID
    resource: str
    action: str
    description: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PermissionCreate(BaseModel):
    """Request model for creating a permission."""
    
    resource: str = Field(..., min_length=1, max_length=50)
    action: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=1, max_length=255)


# Role Schemas
class RoleResponse(BaseModel):
    """Response model for a role."""
    
    id: UUID
    code: str
    name: str
    description: str | None = None
    is_system_role: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class RoleDetailResponse(RoleResponse):
    """Detailed response model for a role with permissions."""
    
    permissions: list[PermissionResponse] = []
    user_count: int = 0


class RoleCreate(BaseModel):
    """Request model for creating a role."""
    
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)


class RoleUpdate(BaseModel):
    """Request model for updating a role."""
    
    name: str | None = Field(None, min_length=1, max_length=120)
    description: str | None = Field(None, max_length=1000)
    is_active: bool | None = None


class RolePermissionAssign(BaseModel):
    """Request model for assigning a permission to a role."""
    
    permission_id: UUID


class RolePermissionRemove(BaseModel):
    """Request model for removing a permission from a role."""
    
    permission_id: UUID


# User Role Assignment Schemas
class UserRoleResponse(BaseModel):
    """Response model for a user role assignment."""
    
    id: UUID
    user_id: UUID
    role_id: UUID
    role: RoleResponse
    assigned_by: UUID
    assigned_at: datetime
    
    class Config:
        from_attributes = True


class UserRoleAssign(BaseModel):
    """Request model for assigning a role to a user."""
    
    role_id: UUID


class UserRoleAssignByCode(BaseModel):
    """Request model for assigning a role to a user by role code."""
    
    role_code: str = Field(..., min_length=1, max_length=50)


class UserRoleRemove(BaseModel):
    """Request model for removing a role from a user."""
    
    role_id: UUID


class UserPermissionResponse(BaseModel):
    """Response model for a user's permissions."""
    
    user_id: UUID
    roles: list[RoleResponse]
    permissions: list[PermissionResponse]


# Authorization check response
class PermissionCheckResponse(BaseModel):
    """Response model for permission check."""
    
    user_id: UUID
    resource: str
    action: str
    has_permission: bool


class MultiPermissionCheckResponse(BaseModel):
    """Response model for checking multiple permissions."""
    
    user_id: UUID
    permissions: dict[str, bool]  # Maps "resource:action" -> has_permission


# Bulk operations
class RolePermissionBulkAssign(BaseModel):
    """Request model for assigning multiple permissions to a role."""
    
    permission_ids: list[UUID]


class RolePermissionBulkRemove(BaseModel):
    """Request model for removing multiple permissions from a role."""
    
    permission_ids: list[UUID]


class UserRoleBulkAssign(BaseModel):
    """Request model for assigning multiple roles to a user."""
    
    role_ids: list[UUID]
