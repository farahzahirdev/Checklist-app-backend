"""
User and Customer Management Schemas

Separate schemas for managing admins/auditors vs customers based on
fixed permission restrictions.
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# User Management (Admins/Auditors)

# Admin and Auditor Creation

class CreateAdminRequest(BaseModel):
    """Request to create a new admin user with all admin permissions."""
    
    email: str = Field(..., description="Admin email address")
    password: str = Field(..., min_length=8, description="Strong password (min 8 chars)")
    reason: str | None = Field(None, max_length=500, description="Reason for creating this admin")


class CreateAuditorRequest(BaseModel):
    """Request to create a new auditor user with read-only permissions."""
    
    email: str = Field(..., description="Auditor email address")
    password: str = Field(..., min_length=8, description="Strong password (min 8 chars)")
    reason: str | None = Field(None, max_length=500, description="Reason for creating this auditor")
    custom_permissions: list[tuple[str, str]] | None = Field(
        None,
        description="Optional custom permissions instead of default auditor permissions"
    )


class CreateAdminResponse(BaseModel):
    """Response after creating an admin user."""
    
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    permissions_assigned: list[dict] = Field(
        default=[],
        description="List of all permissions granted"
    )
    message: str = "Admin user created successfully with full system access"
    
    class Config:
        from_attributes = True


class CreateAuditorResponse(BaseModel):
    """Response after creating an auditor user."""
    
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    permissions_assigned: list[dict] = Field(
        default=[],
        description="List of all permissions granted"
    )
    message: str = "Auditor user created successfully with read-only access"
    
    class Config:
        from_attributes = True


class UserChangeRoleRequest(BaseModel):
    """Request to change a user's role."""
    
    new_role_code: str = Field(..., pattern="^(admin|auditor)$")
    reason: str | None = Field(None, max_length=500)


class UserResponse(BaseModel):
    """Response model for a user."""
    
    id: UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserDetailResponse(UserResponse):
    """Detailed user response with permissions."""
    
    permissions: list[dict] = []
    roles_assigned: list[dict] = []


class UserAssignPermissionsRequest(BaseModel):
    """Request to assign permissions to auditor."""
    
    permissions: list[tuple[str, str]] = Field(
        ..., 
        description="List of (resource, action) permission tuples"
    )


class UserResetPermissionsRequest(BaseModel):
    """Request to reset user permissions to default."""
    
    confirm: bool = Field(
        ..., 
        description="Must be true to confirm reset"
    )


class UserPasswordResetRequest(BaseModel):
    """Request to reset a user's password from admin panel."""

    new_password: str = Field(..., min_length=8)
    reason: str | None = Field(None, max_length=500)


class UserPasswordResetResponse(BaseModel):
    """Response after resetting a password."""

    user_id: UUID
    email: str
    message: str
    reset_at: datetime


# Customer Management (Fixed Permissions)

class CustomerResponse(BaseModel):
    """Response model for a customer user."""
    
    id: UUID
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
    
    # Note: role field not included - customers are always "customer"
    # Note: permissions field not included - always fixed


class CustomerDetailResponse(CustomerResponse):
    """Detailed customer response with fixed permissions."""
    
    permissions: list[dict] = Field(
        default=[
            {"resource": "checklist", "action": "read"},
            {"resource": "assessment", "action": "read"},
            {"resource": "assessment", "action": "create"},
            {"resource": "assessment", "action": "update"},
            {"resource": "assessment_submit", "action": "submit"},
            {"resource": "dashboard", "action": "read"},
            {"resource": "report", "action": "read"},
        ],
        description="Fixed permissions for all customers (read-only)"
    )


class CustomerBanRequest(BaseModel):
    """Request to deactivate a customer account."""
    
    reason: str | None = Field(None, max_length=500)
    permanent: bool = Field(False, description="If true, cannot be reactivated")


class CustomerActivateRequest(BaseModel):
    """Request to reactivate a customer account."""
    
    reason: str | None = Field(None, max_length=500)


# Admin Testing/Role Switching

class AdminRoleSwitchRequest(BaseModel):
    """Request for admin to switch to different role for testing."""
    
    switch_to_role: str = Field(
        ..., 
        pattern="^(admin|auditor|customer)$",
        description="Role to test as"
    )
    reason: str = Field(
        ..., 
        min_length=10,
        max_length=500,
        description="Reason for role switch (must be logged)"
    )
    duration_minutes: int = Field(
        default=30,
        ge=5,
        le=480,
        description="How long to test (5-480 minutes)"
    )


class AdminRoleSwitchResponse(BaseModel):
    """Response for role switch request."""
    
    switched_to_role: str
    temporary_token: str
    expires_at: datetime
    original_role: str = "admin"


class AdminRoleSwitchEndRequest(BaseModel):
    """Request to end role switch and return to admin."""
    
    confirm: bool = Field(True, description="Must confirm to end switch")


# Dashboard Access

class CustomerDashboardAccessRequest(BaseModel):
    """Admin request to view customer dashboard."""
    
    customer_id: UUID
    reason: str | None = Field(None, max_length=500)


class DashboardDataResponse(BaseModel):
    """Dashboard data response (varies by role)."""
    
    user_id: UUID
    user_role: str
    viewed_as_role: str | None = None  # If admin viewing as other role
    
    if_customer: dict | None = None  # Customer dashboard data
    if_auditor: dict | None = None   # Auditor dashboard data
    if_admin: dict | None = None     # Admin dashboard data


# List responses

class UserListResponse(BaseModel):
    """Paginated list of users."""
    
    total: int
    users: list[UserResponse]
    skip: int
    limit: int


class CustomerListResponse(BaseModel):
    """Paginated list of customers."""
    
    total: int
    customers: list[CustomerResponse]
    skip: int
    limit: int
