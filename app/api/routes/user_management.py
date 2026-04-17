"""
User and Customer Management Routes

Separate endpoints for managing:
- Admins and Auditors (managed by admin, permissions can be customized)
- Customers (managed separately, permissions always fixed)
- Admin role switching for testing
- Dashboard access control
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User, UserRole
from app.schemas.user_management import (
    CustomerActivateRequest,
    CustomerBanRequest,
    CustomerDetailResponse,
    CustomerListResponse,
    CustomerResponse,
    AdminRoleSwitchRequest,
    AdminRoleSwitchResponse,
    AdminRoleSwitchEndRequest,
    CustomerDashboardAccessRequest,
    DashboardDataResponse,
    UserAssignPermissionsRequest,
    UserChangeRoleRequest,
    UserDetailResponse,
    UserListResponse,
    UserResetPermissionsRequest,
    UserResponse,
)
from app.services.rbac import RBACService
from app.services.user_management import UserManagementService, FixedPermissionSet


router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# USER MANAGEMENT ROUTES (Admins and Auditors only)
# ============================================================================

@router.get("/users", response_model=UserListResponse)
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    List all users that admin can manage (admin and auditor users).
    
    Notes:
    - Customers are managed via separate API
    - Only admins can call this endpoint
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    manageable = UserManagementService.get_manageable_users(db, current_user.id)
    total = len(manageable)
    users = manageable[skip : skip + limit]
    
    return {
        "total": total,
        "users": users,
        "skip": skip,
        "limit": limit,
    }


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get details of a specific user (admin/auditor only)."""
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Only return manageable users (not customers)
    if user.role == UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use customer management API for customers"
        )
    
    permissions = RBACService.get_user_permissions(db, user_id)
    roles = RBACService.get_user_roles(db, user_id)
    
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "permissions": [{"resource": p.resource, "action": p.action} for p in permissions],
        "roles_assigned": [{"code": r.code, "name": r.name} for r in roles],
    }


@router.patch("/users/{user_id}/role")
def change_user_role(
    user_id: UUID,
    request: UserChangeRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> UserResponse:
    """
    Change a user's role (admin/auditor only).
    
    Rules:
    - Admin can change auditors to admin or demote to auditor
    - Admin can demote other admins to auditor
    - Cannot change customer roles via this endpoint
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if user.role == UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Use customer management API for customers"
        )
    
    try:
        updated_user = UserManagementService.change_user_role(
            db, user_id, request.new_role_code, current_user.id
        )
        return updated_user
    except (ValueError, PermissionError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/users/{user_id}/permissions")
def assign_permissions_to_user(
    user_id: UUID,
    request: UserAssignPermissionsRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Assign custom permissions to an auditor.
    
    Rules:
    - Only for auditors, not customers (customers have fixed permissions)
    - Replaces existing custom permissions
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not UserManagementService.can_modify_user_permissions(user.role, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot modify permissions for {user.role} users"
        )
    
    try:
        UserManagementService.assign_custom_permissions_to_auditor(
            db, user_id, request.permissions, current_user.id
        )
        return {"status": "success", "message": "Permissions updated"}
    except (ValueError, PermissionError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/users/{user_id}/permissions/reset")
def reset_user_permissions(
    user_id: UUID,
    request: UserResetPermissionsRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Reset user permissions to default for their role."""
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm reset"
        )
    
    try:
        UserManagementService.reset_permissions_for_role(db, user_id, current_user.id)
        return {"status": "success", "message": "Permissions reset to default"}
    except (ValueError, PermissionError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# CUSTOMER MANAGEMENT ROUTES (Separate API for customers)
# ============================================================================

@router.get("/customers", response_model=CustomerListResponse)
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    List all customers.
    
    Notes:
    - Customers have fixed permissions (cannot be modified)
    - Only admins can view this list
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    customers = UserManagementService.get_customers(db, skip, limit)
    total = db.query(User).filter(User.role == UserRole.customer.value).count()
    
    return {
        "total": total,
        "customers": customers,
        "skip": skip,
        "limit": limit,
    }


@router.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(
    customer_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get details of a specific customer."""
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a customer"
        )
    
    # Return customer with fixed permissions displayed
    return {
        "id": customer.id,
        "email": customer.email,
        "is_active": customer.is_active,
        "created_at": customer.created_at,
        "updated_at": customer.updated_at,
        "permissions": [
            {"resource": r, "action": a}
            for r, a in FixedPermissionSet.CUSTOMER_PERMISSIONS
        ],
    }


@router.post("/customers/{customer_id}/deactivate")
def deactivate_customer(
    customer_id: UUID,
    request: CustomerBanRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Deactivate (ban) a customer account."""
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a customer"
        )
    
    customer.is_active = False
    db.commit()
    
    return {"status": "success", "message": "Customer deactivated"}


@router.post("/customers/{customer_id}/activate")
def activate_customer(
    customer_id: UUID,
    request: CustomerActivateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Reactivate a deactivated customer account."""
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage users"
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a customer"
        )
    
    customer.is_active = True
    db.commit()
    
    return {"status": "success", "message": "Customer reactivated"}


# ============================================================================
# ADMIN ROLE SWITCH FOR TESTING
# ============================================================================

@router.post("/role-switch", response_model=AdminRoleSwitchResponse)
def switch_admin_role_for_testing(
    request: AdminRoleSwitchRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Allow admin to temporarily switch to another role for testing.
    
    Use Cases:
    - Test customer flow as customer
    - Review what auditor can see
    - Test permission scenarios
    
    Returns temporary token valid for specified duration.
    """
    if current_user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can switch roles"
        )
    
    # TODO: Generate temporary JWT with different role claim
    # TODO: Log this action for audit trail
    
    from datetime import datetime, timedelta
    from app.core.security import create_access_token
    
    expires_at = datetime.utcnow() + timedelta(minutes=request.duration_minutes)
    
    # Create temporary token with switched role (for testing purposes)
    temp_token = create_access_token(
        user_id=str(current_user.id),
        role=request.switch_to_role,
        ttl_minutes=request.duration_minutes
    )
    
    return {
        "switched_to_role": request.switch_to_role,
        "temporary_token": temp_token,
        "expires_at": expires_at,
        "original_role": current_user.role,
    }


@router.post("/role-switch/end")
def end_admin_role_switch(
    request: AdminRoleSwitchEndRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """End role switch and return to admin role."""
    if current_user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User must be admin (or role switch must have expired)"
        )
    
    return {"status": "success", "message": "Returned to admin role"}


# ============================================================================
# DASHBOARD ACCESS CONTROL
# ============================================================================

@router.post("/customers/{customer_id}/dashboard")
def view_customer_dashboard_as_admin(
    customer_id: UUID,
    request: CustomerDashboardAccessRequest | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Allow admin to view customer's dashboard to understand their experience.
    
    Useful for:
    - Debugging customer issues
    - Testing new features as customer
    - Understanding user flow
    
    Returns dashboard data with role info showing admin viewed it.
    """
    if not RBACService.has_permission(db, current_user.id, "dashboard", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a customer"
        )
    
    # TODO: Load actual customer dashboard data
    # For now, return structure showing admin viewing as customer
    
    return {
        "user_id": customer_id,
        "user_role": "customer",
        "viewed_as_role": current_user.role,  # Shows admin viewing it
        "if_customer": {
            # Customer-specific dashboard data would go here
            "recent_assessments": [],
            "payment_status": None,
            "available_checklists": [],
        },
    }
