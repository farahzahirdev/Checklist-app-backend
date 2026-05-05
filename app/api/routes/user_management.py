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

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.core.security import hash_password
from app.models.audit_log import AuditAction, AuditLog
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate
from app.models.user import User, UserRole
from app.schemas.user_management import (
    CreateAdminRequest,
    CreateAdminResponse,
    CreateAuditorRequest,
    CreateAuditorResponse,
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
    UserPasswordResetRequest,
    UserPasswordResetResponse,
    UserResponse,
)
from app.services.rbac import RBACService
from app.services.user_management import UserManagementService, FixedPermissionSet
from app.services.auth import get_password_validation_error
from app.services.customer_payments import (
    get_customer_payment_dashboard,
    get_customer_payment_records,
)
from app.services.customer_assessments import (
    get_customer_assessments,
    get_customer_dashboard_enhanced,
)


router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# USER MANAGEMENT ROUTES (Admins and Auditors only)
# ============================================================================

@router.post("/users/create-admin", response_model=CreateAdminResponse, status_code=status.HTTP_201_CREATED)
def create_admin_user(
    request: Request,
    payload: CreateAdminRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Create a new admin user with full system access.
    
    Admin users get ALL permissions:
    - checklist: read, create, update
    - checklist_admin: create, update, delete, manage
    - assessment: read, create, update, submit
    - dashboard: read
    - report: read, create
    - user_management: read, manage
    - payment_management: read, manage
    - permission_management: manage
    - audit_log: read, manage
    
    Only admins can create other admins.
    """
    lang_code = get_language_code(request, db)
    
    # Check permission
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )
    
    # Validate email uniqueness
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("email_already_exists", lang_code)
        )
    
    # Validate password
    validation_error = get_password_validation_error(payload.password)
    if validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate(validation_error, lang_code)
        )
    
    # Create admin user with all admin permissions
    try:
        password_hash = hash_password(payload.password)
        new_admin = UserManagementService.create_user_with_role(
            db,
            email=payload.email,
            password_hash=password_hash,
            role_code="admin"
        )
        
        # Log audit trail
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                actor_role=str(current_user.role),
                action=AuditAction.user_created,
                target_entity="user",
                target_id=new_admin.id,
                target_user_id=new_admin.id,
                changes_summary=f"Created admin user: {payload.reason or 'No reason provided'}",
            )
        )
        db.commit()
        db.refresh(new_admin)
        
        # Get all permissions assigned
        permissions = RBACService.get_user_permissions(db, new_admin.id)
        
        return {
            "id": new_admin.id,
            "email": new_admin.email,
            "role": new_admin.role,
            "is_active": new_admin.is_active,
            "created_at": new_admin.created_at,
            "permissions_assigned": [
                {"resource": p.resource, "action": p.action}
                for p in permissions
            ],
            "message": "Admin user created successfully with full system access"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/users/create-auditor", response_model=CreateAuditorResponse, status_code=status.HTTP_201_CREATED)
def create_auditor_user(
    request: Request,
    payload: CreateAuditorRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Create a new auditor user with read-only permissions.
    
    Auditor users get read-only permissions:
    - checklist: read
    - assessment: read
    - dashboard: read
    - report: read
    - user_management: read
    - payment_management: read
    - audit_log: read
    
    Optionally, custom permissions can be assigned instead of defaults.
    Only admins can create auditors.
    """
    lang_code = get_language_code(request, db)
    
    # Check permission
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )
    
    # Validate email uniqueness
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("email_already_exists", lang_code)
        )
    
    # Validate password
    validation_error = get_password_validation_error(payload.password)
    if validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate(validation_error, lang_code)
        )
    
    # Create auditor user with default or custom permissions
    try:
        password_hash = hash_password(payload.password)
        new_auditor = UserManagementService.create_user_with_role(
            db,
            email=payload.email,
            password_hash=password_hash,
            role_code="auditor"
        )
        
        # If custom permissions provided, assign them
        if payload.custom_permissions:
            UserManagementService.assign_custom_permissions_to_auditor(
                db,
                new_auditor.id,
                payload.custom_permissions,
                current_user.id
            )
        
        # Log audit trail
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                actor_role=str(current_user.role),
                action=AuditAction.user_created,
                target_entity="user",
                target_id=new_auditor.id,
                target_user_id=new_auditor.id,
                changes_summary=f"Created auditor user: {payload.reason or 'No reason provided'}",
            )
        )
        db.commit()
        db.refresh(new_auditor)
        
        # Get all permissions assigned
        permissions = RBACService.get_user_permissions(db, new_auditor.id)
        
        return {
            "id": new_auditor.id,
            "email": new_auditor.email,
            "role": new_auditor.role,
            "is_active": new_auditor.is_active,
            "created_at": new_auditor.created_at,
            "permissions_assigned": [
                {"resource": p.resource, "action": p.action}
                for p in permissions
            ],
            "message": "Auditor user created successfully with read-only access"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )



@router.get("/users", response_model=UserListResponse)
def list_users(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Filter by email or role"),
    role: str | None = Query(None, description="Filter by exact role"),
    is_active: bool | None = Query(None, description="Filter by active status (None=show all)"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    List all users that admin can manage (admin and auditor users).
    
    Notes:
    - Customers are managed via separate API
    - Admins and auditors can call this endpoint
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )

    query = db.query(User).filter(
        User.role.in_([UserRole.admin.value, UserRole.auditor.value]),
    )

    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.email.ilike(search_term),
                User.role.ilike(search_term),
            )
        )

    sort_column = User.created_at
    if sort_by == "email":
        sort_column = User.email
    elif sort_by == "role":
        sort_column = User.role
    elif sort_by == "updated_at":
        sort_column = User.updated_at

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    users = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "users": users,
        "skip": skip,
        "limit": limit,
    }


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get details of a specific user (admin/auditor only)."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))
    
    # Only return manageable users (not customers)
    if user.role == UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("use_customer_management_api_for_customers", lang_code)
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
    request: Request,
    payload: UserChangeRoleRequest,
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
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )
    
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("cannot_change_your_own_role", lang_code)
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))
    
    if user.role == UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("use_customer_management_api_for_customers", lang_code)
        )
    
    try:
        updated_user = UserManagementService.change_user_role(
            db, user_id, payload.new_role_code, current_user.id
        )
        return updated_user
    except (ValueError, PermissionError) as e:
        translated_detail = translate(str(e), lang_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translated_detail if translated_detail != str(e) else str(e)
        )


@router.post("/users/{user_id}/permissions")
def assign_permissions_to_user(
    user_id: UUID,
    request: Request,
    payload: UserAssignPermissionsRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Assign custom permissions to an auditor.
    
    Rules:
    - Only for auditors, not customers (customers have fixed permissions)
    - Replaces existing custom permissions
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))
    
    if not UserManagementService.can_modify_user_permissions(user.role, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{translate('cannot_modify_permissions_for_role_users', lang_code)} {user.role}"
        )
    
    try:
        UserManagementService.assign_custom_permissions_to_auditor(
            db, user_id, payload.permissions, current_user.id
        )
        return {"status": "success", "message": translate("permissions_updated", lang_code)}
    except (ValueError, PermissionError) as e:
        translated_detail = translate(str(e), lang_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translated_detail if translated_detail != str(e) else str(e)
        )


@router.post("/users/{user_id}/permissions/reset")
def reset_user_permissions(
    user_id: UUID,
    request: Request,
    payload: UserResetPermissionsRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Reset user permissions to default for their role."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("must_confirm_reset", lang_code)
        )
    
    try:
        UserManagementService.reset_permissions_for_role(db, user_id, current_user.id)
        return {"status": "success", "message": translate("permissions_reset_to_default", lang_code)}
    except (ValueError, PermissionError) as e:
        translated_detail = translate(str(e), lang_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translated_detail if translated_detail != str(e) else str(e)
        )


@router.post("/users/{user_id}/password/reset", response_model=UserPasswordResetResponse)
def reset_user_password(
    user_id: UUID,
    request: Request,
    payload: UserPasswordResetRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Reset a user's password from the admin panel."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))

    validation_error = get_password_validation_error(payload.new_password)
    if validation_error is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=translate(validation_error, lang_code))

    user.password_hash = hash_password(payload.new_password)
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            actor_role=str(current_user.role),
            action=AuditAction.auth_password_change,
            target_entity="user",
            target_id=user.id,
            target_user_id=user.id,
            changes_summary=payload.reason or "Admin reset user password",
        )
    )
    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "message": "Password reset successfully.",
        "reset_at": user.updated_at,
    }


# ============================================================================
# CUSTOMER MANAGEMENT ROUTES (Separate API for customers)
# ============================================================================

@router.get("/customers", response_model=CustomerListResponse)
def list_customers(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    sort_by: str | None = Query(None, description="Field to sort by"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    search: str | None = Query(None, description="Filter by email"),
    is_active: bool | None = Query(None, description="Filter active/inactive customers"),
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    List all customers.
    
    Notes:
    - Customers have fixed permissions (cannot be modified)
    - Admins and auditors can view this list
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )

    query = db.query(User).filter(User.role == UserRole.customer.value)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)

    if search:
        search_term = f"%{search}%"
        query = query.filter(User.email.ilike(search_term))

    sort_column = User.created_at
    if sort_by == "email":
        sort_column = User.email
    elif sort_by == "updated_at":
        sort_column = User.updated_at

    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)

    total = query.count()
    customers = query.offset(skip).limit(limit).all()

    return {
        "total": total,
        "customers": customers,
        "skip": skip,
        "limit": limit,
    }


@router.get("/customers/{customer_id}", response_model=CustomerDetailResponse)
def get_customer(
    customer_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get details of a specific customer."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("customer_not_found", lang_code))
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("user_is_not_a_customer", lang_code)
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
    request: Request,
    payload: CustomerBanRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Deactivate (ban) a customer account."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("customer_not_found", lang_code))
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("user_is_not_a_customer", lang_code)
        )
    
    customer.is_active = False
    db.commit()
    
    return {"status": "success", "message": translate("customer_deactivated", lang_code)}


@router.post("/customers/{customer_id}/activate")
def activate_customer(
    customer_id: UUID,
    request: Request,
    payload: CustomerActivateRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Reactivate a deactivated customer account."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_manage_users", lang_code)
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("customer_not_found", lang_code))
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("user_is_not_a_customer", lang_code)
        )
    
    customer.is_active = True
    db.commit()
    
    return {"status": "success", "message": translate("customer_reactivated", lang_code)}


# ============================================================================
# ADMIN ROLE SWITCH FOR TESTING
# ============================================================================

@router.post("/role-switch", response_model=AdminRoleSwitchResponse)
def switch_admin_role_for_testing(
    request: Request,
    payload: AdminRoleSwitchRequest,
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
    lang_code = get_language_code(request, db)
    if current_user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("only_admins_can_switch_roles", lang_code)
        )
    
    # TODO: Generate temporary JWT with different role claim
    # TODO: Log this action for audit trail
    
    from datetime import datetime, timedelta
    from app.core.security import create_access_token
    
    expires_at = datetime.utcnow() + timedelta(minutes=payload.duration_minutes)
    
    # Remove all existing roles for the user (simulate switch)
    from app.models.rbac import UserRoleAssignment
    db.query(UserRoleAssignment).filter(UserRoleAssignment.user_id == current_user.id).delete()
    db.commit()

    # Assign the switched role
    from app.services.rbac import RBACService
    RBACService.assign_role_by_code(db, current_user.id, payload.switch_to_role, current_user.id)
    db.commit()

    # Create temporary token with switched role (for testing purposes)
    temp_token = create_access_token(
        user_id=str(current_user.id),
        role=payload.switch_to_role,
        ttl_minutes=payload.duration_minutes
    )

    return {
        "switched_to_role": payload.switch_to_role,
        "temporary_token": temp_token,
        "expires_at": expires_at,
        "original_role": current_user.role,
        "note": "User's roles in the database have been temporarily switched for testing. Remember to revert after testing."
    }


@router.post("/role-switch/end")
def end_admin_role_switch(
    request: Request,
    payload: AdminRoleSwitchEndRequest,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """End role switch and return to admin role."""
    lang_code = get_language_code(request, db)
    if current_user.role != UserRole.admin.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("user_must_be_admin_or_role_switch_must_have_expired", lang_code)
        )
    
    return {"status": "success", "message": translate("returned_to_admin_role", lang_code)}


# ============================================================================
# DASHBOARD ACCESS CONTROL
# ============================================================================

@router.post("/customers/{customer_id}/dashboard")
def view_customer_dashboard_as_admin(
    customer_id: UUID,
    request: Request,
    payload: CustomerDashboardAccessRequest | None = None,
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
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "dashboard", "read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    customer = db.query(User).filter(User.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("customer_not_found", lang_code))
    
    if customer.role != UserRole.customer.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=translate("user_is_not_a_customer", lang_code)
        )

    payment_dashboard = get_customer_payment_dashboard(db, customer_id)
    payment_records = get_customer_payment_records(db, customer_id, skip=0, limit=100)
    assessment_dashboard = get_customer_dashboard_enhanced(db, user_id=customer_id, lang_code=lang_code)
    assessment_records = get_customer_assessments(db, user_id=customer_id, skip=0, limit=100, lang_code=lang_code)

    return {
        "user_id": customer_id,
        "user_role": "customer",
        "viewed_as_role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        "if_customer": {
            "payment_dashboard": payment_dashboard.model_dump(mode="json"),
            "payment_records": payment_records.model_dump(mode="json"),
            "assessment_dashboard": assessment_dashboard.model_dump(mode="json"),
            "assessment_records": assessment_records.model_dump(mode="json"),
        },
    }
