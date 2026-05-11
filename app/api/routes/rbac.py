"""
RBAC Admin Routes

Administrative endpoints for managing roles, permissions, and user role assignments.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.dependencies import get_db
from app.utils.i18n import get_language_code
from app.utils.i18n_messages import translate
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
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[Permission]:
    """
    List all permissions.
    
    Requires: permission_management:read (for viewing) or permission_management:manage (for full access)
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    return db.query(Permission).offset(skip).limit(limit).all()


@router.get("/permissions/{permission_id}", response_model=PermissionResponse)
def get_permission(
    permission_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Permission:
    """Get a specific permission."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    permission = db.query(Permission).filter(Permission.id == permission_id).first()
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("permission_not_found", lang_code))
    
    return permission


@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(
    request: Request,
    payload: PermissionCreate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Permission:
    """
    Create a new permission.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Check if permission already exists
    existing = db.query(Permission).filter(
        Permission.resource == payload.resource,
        Permission.action == payload.action
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate("permission_already_exists", lang_code)
        )
    
    permission = Permission(
        resource=payload.resource,
        action=payload.action,
        description=payload.description
    )
    db.add(permission)
    db.commit()
    db.refresh(permission)
    return permission


# Role endpoints

@router.get("/roles", response_model=list[RoleResponse])
def list_roles(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[Role]:
    """List all roles."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    return db.query(Role).offset(skip).limit(limit).all()


@router.get("/roles/{role_id}", response_model=RoleDetailResponse)
def get_role(
    role_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get a specific role with its permissions."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
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
    request: Request,
    payload: RoleCreate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Role:
    """
    Create a new role.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Check if role code already exists
    existing = db.query(Role).filter(Role.code == payload.code).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=translate("role_code_already_exists", lang_code)
        )
    
    role = Role(
        code=payload.code,
        name=payload.name,
        description=payload.description
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.patch("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    request: Request,
    payload: RoleUpdate,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Role:
    """
    Update a role.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    if role.is_system_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("cannot_modify_system_roles", lang_code)
        )
    
    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    if payload.is_active is not None:
        role.is_active = payload.is_active
    
    db.commit()
    db.refresh(role)
    return role


# Role-Permission endpoints

@router.post("/roles/{role_id}/permissions", response_model=PermissionResponse)
def assign_permission_to_role(
    role_id: UUID,
    request: Request,
    payload: RolePermissionAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> Permission:
    """
    Assign a permission to a role.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    permission = db.query(Permission).filter(Permission.id == payload.permission_id).first()
    if not permission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("permission_not_found", lang_code))
    
    RBACService.add_permission_to_role(db, role_id, payload.permission_id)
    return permission


@router.post("/roles/{role_id}/permissions/bulk", status_code=status.HTTP_204_NO_CONTENT)
def assign_permissions_bulk(
    role_id: UUID,
    request: Request,
    payload: RolePermissionBulkAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Assign multiple permissions to a role.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    for permission_id in payload.permission_ids:
        permission = db.query(Permission).filter(Permission.id == permission_id).first()
        if permission:
            RBACService.add_permission_to_role(db, role_id, permission_id)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_permission_from_role(
    role_id: UUID,
    permission_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove a permission from a role.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    RBACService.remove_permission_from_role(db, role_id, permission_id)


@router.post("/roles/{role_id}/permissions/bulk-remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_permissions_bulk(
    role_id: UUID,
    request: Request,
    payload: RolePermissionBulkRemove,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove multiple permissions from a role.
    
    Requires: permission_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "permission_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    for permission_id in payload.permission_ids:
        RBACService.remove_permission_from_role(db, role_id, permission_id)


# User-Role endpoints

@router.get("/users/{user_id}/roles", response_model=list[UserRoleResponse])
def get_user_roles(
    user_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> list[UserRoleAssignment]:
    """Get all roles assigned to a user."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        # Users can see their own roles
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate("insufficient_permissions", lang_code)
            )
    
    return db.query(UserRoleAssignment).filter(
        UserRoleAssignment.user_id == user_id
    ).all()


@router.get("/users/{user_id}/permissions", response_model=UserPermissionResponse)
def get_user_permissions(
    user_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """Get all permissions available to a user."""
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "read") and \
       not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        # Users can see their own permissions
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate("insufficient_permissions", lang_code)
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
    request: Request,
    payload: UserRoleAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> UserRoleAssignment:
    """
    Assign a role to a user.
    
    Requires: user_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))
    
    # Verify role exists
    role = db.query(Role).filter(Role.id == payload.role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    assignment = RBACService.assign_role_to_user(db, user_id, payload.role_id, current_user.id)
    return assignment


@router.post("/users/{user_id}/roles/by-code", response_model=UserRoleResponse, status_code=status.HTTP_201_CREATED)
def assign_role_to_user_by_code(
    user_id: UUID,
    request: Request,
    payload: UserRoleAssignByCode,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> UserRoleAssignment:
    """
    Assign a role to a user by role code (e.g., 'admin', 'auditor', 'customer').
    
    Requires: user_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))
    
    assignment = RBACService.assign_role_by_code(db, user_id, payload.role_code, current_user.id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("role_not_found", lang_code))
    
    return assignment


@router.post("/users/{user_id}/roles/bulk", status_code=status.HTTP_204_NO_CONTENT)
def assign_roles_bulk(
    user_id: UUID,
    request: Request,
    payload: UserRoleBulkAssign,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Assign multiple roles to a user.
    
    Requires: user_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=translate("user_not_found", lang_code))
    
    for role_id in payload.role_ids:
        role = db.query(Role).filter(Role.id == role_id).first()
        if role:
            RBACService.assign_role_to_user(db, user_id, role_id, current_user.id)


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> None:
    """
    Remove a role from a user.
    
    Requires: user_management:manage
    """
    lang_code = get_language_code(request, db)
    if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=translate("insufficient_permissions", lang_code)
        )
    
    RBACService.remove_role_from_user(db, user_id, role_id)


# Permission check endpoints

@router.post("/check-permission", response_model=PermissionCheckResponse)
def check_permission(
    resource: str,
    action: str,
    request: Request,
    user_id: UUID | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Check if a user has a specific permission.
    
    If user_id is not provided, checks current user's permissions.
    """
    lang_code = get_language_code(request, db)
    if user_id is None:
        user_id = current_user.id
    
    # Only allow checking own permissions unless admin
    if user_id != current_user.id:
        if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate("cannot_check_another_users_permissions", lang_code)
            )
    
    has_permission = RBACService.check_permission(db, user_id, resource, action)
    
    return {
        "user_id": user_id,
        "resource": resource,
        "action": action,
        "has_permission": has_permission,
    }


@router.post("/check-permissions", response_model=MultiPermissionCheckResponse)
def check_multiple_permissions(
    permissions: list[tuple[str, str]],
    request: Request,
    user_id: UUID | None = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> dict:
    """
    Check if a user has multiple permissions.
    
    If user_id is not provided, checks current user's permissions.
    """
    lang_code = get_language_code(request, db)
    if user_id is None:
        user_id = current_user.id
    
    # Only allow checking own permissions unless admin
    if user_id != current_user.id:
        if not RBACService.has_permission(db, current_user.id, "user_management", "manage"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=translate("cannot_check_another_users_permissions", lang_code)
            )
    
    permission_checks = RBACService.check_multiple_permissions(db, user_id, permissions)
    
    return {
        "user_id": user_id,
        "permissions": permission_checks,
    }
