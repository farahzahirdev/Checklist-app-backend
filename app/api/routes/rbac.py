"""
RBAC Admin Routes

Administrative endpoints for managing roles, permissions, and user role assignments.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.rbac import Permission, Role, UserRoleAssignment
from app.schemas.rbac import (
    MultiPermissionCheckResponse,
    PermissionCheckResponse,
    PermissionCreate,
    PermissionResponse,
    RoleCreate,
    RoleDetailResponse,
    RolePermissionAssign,
    RolePermissionBulkAssign,
    RolePermissionBulkRemove,
    RolePermissionRemove,
    RoleResponse,
    RoleUpdate,
    UserPermissionResponse,
    UserRoleAssign,
    UserRoleAssignByCode,
    UserRoleBulkAssign,
    UserRoleRemove,
    UserRoleResponse,
)
from app.services.rbac import RBACService


router = APIRouter(prefix="/admin/rbac", tags=["admin", "rbac"])


# Permission endpoints

@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[Permission]:
    """
    List all permissions.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    return db.query(Permission).offset(skip).limit(limit).all()


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
def get_permission(
    permission_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Permission:
    """Get a specific permission."""
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    
    return permission


@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(
    request: PermissionCreate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Permission:
    """
    Create a new permission.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Check if permission already exists
    existing = db.query(Permission).filter(
        Permission.resource == request.resource,
        Permission.action == request.action
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Permission already exists"
        )
    
    permission = Permission(
        resource=request.resource,
        action=request.action,
        description=request.description
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


# Role endpoints

@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[Role]:
    """List all roles."""
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    return db.query(Role).offset(skip).limit(limit).all()


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
def get_role(
    role_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get a specific role with its permissions."""
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    # Get role permissions
    permissions = [rp.permission for rp in role.role_permissions]
    
    # Get user count
    user_count = db.query(UserRoleAssignment).filter(
        UserRoleAssignment.role_id == role_id
    ).count()
    
    return {
        **{c.name: getattr(role, c.name) for c in role.__table__.columns},
        "permissions": permissions,
        "user_count": user_count,
    }


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(
    request: RoleCreate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Role:
    """
    Create a new role.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Check if role code already exists
    existing = db.query(Role).filter(Role.code == request.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role code already exists"
        )
    
    role = Role(
        code=request.code,
        name=request.name,
        description=request.description
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.patch("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    request: RoleUpdate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Role:
    """
    Update a role.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system roles"
        )
    
    if request.name is not None:
        role.name = request.name
    if request.description is not None:
        role.description = request.description
    if request.is_active is not None:
        role.is_active = request.is_active
    
    db.commit()
    db.refresh(role)
    return role


# Role-Permission endpoints

@router.post("/roles/{role_id}/permissions", response_model=PermissionResponse)
def assign_permission_to_role(
    role_id: UUID,
    request: RolePermissionAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Permission:
    """
    Assign a permission to a role.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    permission = db.query(Permission).filter(Permission.id == request.permission_id).first()
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Permission not found")
    
    RBACService.add_permission_to_role(db, role_id, request.permission_id)
    return permission


@router.post("/roles/{role_id}/permissions/bulk", status_code=status.HTTP_204_NO_CONTENT)
def assign_permissions_bulk(
    role_id: UUID,
    request: RolePermissionBulkAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Assign multiple permissions to a role.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    for permission_id in request.permission_ids:
        permission = db.query(Permission).filter(Permission.id == permission_id).first()
        if permission:
            RBACService.add_permission_to_role(db, role_id, permission_id)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove a permission from a role.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    RBACService.remove_permission_from_role(db, role_id, permission_id)


@router.post("/roles/{role_id}/permissions/bulk-remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_permissions_bulk(
    role_id: UUID,
    request: RolePermissionBulkRemove,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove multiple permissions from a role.
    
    Requires: permission_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    for permission_id in request.permission_ids:
        RBACService.remove_permission_from_role(db, role_id, permission_id)


# User-Role endpoints

@router.get("/users/{user_id}/roles", response_model=list[UserRoleResponse])
def get_user_roles(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[UserRoleAssignment]:
    """Get all roles assigned to a user."""
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        # Users can see their own roles
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    
    return db.query(UserRoleAssignment).filter(
        UserRoleAssignment.user_id == user_id
    ).all()


@router.get("/users/{user_id}/permissions", response_model=UserPermissionResponse)
def get_user_permissions(
    user_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get all permissions available to a user."""
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        # Users can see their own permissions
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
    
    roles = RBACService.get_user_roles(db, user_id)
    permissions = RBACService.get_user_permissions(db, user_id)
    
    return {
        "user_id": user_id,
        "roles": roles,
        "permissions": permissions,
    }


@router.post("/users/{user_id}/roles", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
def assign_role_to_user(
    user_id: UUID,
    request: UserRoleAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> UserRoleAssignment:
    """
    Assign a role to a user.
    
    Requires: user_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    # Verify role exists
    role = db.query(Role).filter(Role.id == request.role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    assignment = RBACService.assign_role_to_user(db, user_id, request.role_id, current_user.id)
    return assignment


@router.post("/users/{user_id}/roles/by-code", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
def assign_role_to_user_by_code(
    user_id: UUID,
    request: UserRoleAssignByCode,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> UserRoleAssignment:
    """
    Assign a role to a user by role code (e.g., 'admin', 'auditor', 'customer').
    
    Requires: user_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    assignment = RBACService.assign_role_by_code(db, user_id, request.role_code, current_user.id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    return assignment


@router.post("/users/{user_id}/roles/bulk", status_code=status.HTTP_204_NO_CONTENT)
def assign_roles_bulk(
    user_id: UUID,
    request: UserRoleBulkAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Assign multiple roles to a user.
    
    Requires: user_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    for role_id in request.role_ids:
        role = db.query(Role).filter(Role.id == role_id).first()
        if role:
            RBACService.assign_role_to_user(db, user_id, role_id, current_user.id)


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove a role from a user.
    
    Requires: user_management:manage
    """
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    RBACService.remove_role_from_user(db, user_id, role_id)


# Permission check endpoints

@router.post("/check-permission", response_model=PermissionCheckResponse)
def check_permission(
    resource: str,
    action: str,
    user_id: UUID | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Check if a user has a specific permission.
    
    If user_id is not provided, checks current user's permissions.
    """
    if user_id is None:
        user_id = current_user.id
    
    # Only allow checking own permissions unless admin
    if user_id != current_user.id:
        if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot check another user's permissions"
            )
    
    has_permission = RBACService.has_permission(db, user_id, resource, action)
    
    return {
        "user_id": user_id,
        "resource": resource,
        "action": action,
        "has_permission": has_permission,
    }


@router.post("/check-permissions", response_model=MultiPermissionCheckResponse)
def check_multiple_permissions(
    permissions: list[tuple[str, str]],
    user_id: UUID | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Check if a user has multiple permissions.
    
    If user_id is not provided, checks current user's permissions.
    """
    if user_id is None:
        user_id = current_user.id
    
    # Only allow checking own permissions unless admin
    if user_id != current_user.id:
        if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot check another user's permissions"
            )
    
    permission_checks = {}
    for resource, action in permissions:
        key = f"{resource}:{action}"
        permission_checks[key] = RBACService.has_permission(db, user_id, resource, action)
    
    return {
        "user_id": user_id,
        "permissions": permission_checks,
    }
