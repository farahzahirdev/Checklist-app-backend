"""
Role-Based Access Control (RBAC) Service

Provides permission checking and role management functionality.
"""
from typing import Optional
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.rbac import (
    Permission,
    PermissionAction,
    PermissionResource,
    Role,
    RolePermission,
    UserRoleAssignment,
)
from app.models.user import User, UserRole


class RBACService:
    """Service for RBAC operations and permission checking."""
    
    @staticmethod
    def get_all_system_roles(db: Session) -> list[Role]:
        """Get all system roles."""
        return db.query(Role).filter(Role.is_system_role == True, Role.is_active == True).all()
    
    @staticmethod
    def get_role_by_code(db: Session, code: str) -> Optional[Role]:
        """Get a role by its code (e.g., 'admin', 'auditor', 'customer')."""
        return db.query(Role).filter(Role.code == code, Role.is_active == True).first()
    
    @staticmethod
    def get_user_roles(db: Session, user_id: uuid.UUID) -> list[Role]:
        """Get all active roles assigned to a user."""
        return db.query(Role).join(
            UserRoleAssignment, UserRoleAssignment.role_id == Role.id
        ).filter(
            UserRoleAssignment.user_id == user_id,
            Role.is_active == True
        ).all()
    
    @staticmethod
    def get_user_permissions(db: Session, user_id: uuid.UUID) -> list[Permission]:
        """Get all permissions available to a user through their assigned roles."""
        return db.query(Permission).distinct().join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).join(
            Role, Role.id == RolePermission.role_id
        ).join(
            UserRoleAssignment, UserRoleAssignment.role_id == Role.id
        ).filter(
            UserRoleAssignment.user_id == user_id,
            Role.is_active == True,
            Permission.is_active == True
        ).all()
    
    @staticmethod
    def has_permission(
        db: Session,
        user_id: uuid.UUID,
        resource: str,
        action: str
    ) -> bool:
        """
        Check if a user has a specific permission.
        
        Args:
            db: Database session
            user_id: User ID to check
            resource: Permission resource (e.g., 'checklist', 'assessment')
            action: Permission action (e.g., 'read', 'write', 'delete')
        
        Returns:
            True if user has the permission, False otherwise
        """
        # Get user to check if active and exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            return False
        
        # Check if permission exists in user's assigned roles
        permission_exists = db.query(Permission).join(
            RolePermission, RolePermission.permission_id == Permission.id
        ).join(
            Role, Role.id == RolePermission.role_id
        ).join(
            UserRoleAssignment, UserRoleAssignment.role_id == Role.id
        ).filter(
            UserRoleAssignment.user_id == user_id,
            Role.is_active == True,
            Permission.is_active == True,
            Permission.resource == resource,
            Permission.action == action
        ).first()
        
        return permission_exists is not None
    
    @staticmethod
    def has_any_permission(
        db: Session,
        user_id: uuid.UUID,
        permissions: list[tuple[str, str]]
    ) -> bool:
        """
        Check if a user has any of the specified permissions.
        
        Args:
            db: Database session
            user_id: User ID to check
            permissions: List of (resource, action) tuples
        
        Returns:
            True if user has at least one of the permissions, False otherwise
        """
        for resource, action in permissions:
            if RBACService.has_permission(db, user_id, resource, action):
                return True
        return False
    
    @staticmethod
    def has_all_permissions(
        db: Session,
        user_id: uuid.UUID,
        permissions: list[tuple[str, str]]
    ) -> bool:
        """
        Check if a user has all of the specified permissions.
        
        Args:
            db: Database session
            user_id: User ID to check
            permissions: List of (resource, action) tuples
        
        Returns:
            True if user has all permissions, False otherwise
        """
        for resource, action in permissions:
            if not RBACService.has_permission(db, user_id, resource, action):
                return False
        return True
    
    @staticmethod
    def assign_role_to_user(
        db: Session,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        assigned_by_user_id: uuid.UUID
    ) -> UserRoleAssignment:
        """
        Assign a role to a user.
        
        Args:
            db: Database session
            user_id: User ID receiving the role
            role_id: Role ID to assign
            assigned_by_user_id: User ID of the admin assigning the role
        
        Returns:
            UserRoleAssignment object
        """
        # Check if assignment already exists
        existing = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id
        ).first()
        
        if existing:
            return existing
        
        assignment = UserRoleAssignment(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by_user_id
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment
    
    @staticmethod
    def assign_role_by_code(
        db: Session,
        user_id: uuid.UUID,
        role_code: str,
        assigned_by_user_id: uuid.UUID
    ) -> Optional[UserRoleAssignment]:
        """
        Assign a role to a user by role code.
        
        Args:
            db: Database session
            user_id: User ID receiving the role
            role_code: Role code (e.g., 'admin', 'auditor', 'customer')
            assigned_by_user_id: User ID of the admin assigning the role
        
        Returns:
            UserRoleAssignment object, or None if role not found
        """
        role = RBACService.get_role_by_code(db, role_code)
        if not role:
            return None
        
        return RBACService.assign_role_to_user(
            db, user_id, role.id, assigned_by_user_id
        )
    
    @staticmethod
    def remove_role_from_user(
        db: Session,
        user_id: uuid.UUID,
        role_id: uuid.UUID
    ) -> bool:
        """
        Remove a role from a user.
        
        Args:
            db: Database session
            user_id: User ID
            role_id: Role ID to remove
        
        Returns:
            True if removed, False if assignment didn't exist
        """
        assignment = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.role_id == role_id
        ).first()
        
        if not assignment:
            return False
        
        db.delete(assignment)
        db.commit()
        return True
    
    @staticmethod
    def get_or_create_permission(
        db: Session,
        resource: str,
        action: str,
        description: str = ""
    ) -> Permission:
        """
        Get or create a permission.
        
        Args:
            db: Database session
            resource: Permission resource
            action: Permission action
            description: Permission description
        
        Returns:
            Permission object
        """
        permission = db.query(Permission).filter(
            Permission.resource == resource,
            Permission.action == action
        ).first()
        
        if permission:
            return permission
        
        permission = Permission(
            resource=resource,
            action=action,
            description=description or f"{resource}:{action}"
        )
        db.add(permission)
        db.commit()
        db.refresh(permission)
        return permission
    
    @staticmethod
    def add_permission_to_role(
        db: Session,
        role_id: uuid.UUID,
        permission_id: uuid.UUID
    ) -> RolePermission:
        """
        Add a permission to a role.
        
        Args:
            db: Database session
            role_id: Role ID
            permission_id: Permission ID
        
        Returns:
            RolePermission object
        """
        # Check if assignment already exists
        existing = db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id
        ).first()
        
        if existing:
            return existing
        
        assignment = RolePermission(
            role_id=role_id,
            permission_id=permission_id
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment
    
    @staticmethod
    def remove_permission_from_role(
        db: Session,
        role_id: uuid.UUID,
        permission_id: uuid.UUID
    ) -> bool:
        """
        Remove a permission from a role.
        
        Args:
            db: Database session
            role_id: Role ID
            permission_id: Permission ID
        
        Returns:
            True if removed, False if assignment didn't exist
        """
        assignment = db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id
        ).first()
        
        if not assignment:
            return False
        
        db.delete(assignment)
        db.commit()
        return True
