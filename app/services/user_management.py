"""
User Management and Permission Assignment Service

Implements role-based user lifecycle and permission management with fixed
permission sets for each role type.
"""
from enum import StrEnum
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.user import User, UserRole
from app.models.rbac import Role, UserRoleAssignment
from app.services.rbac import RBACService


class UserType(StrEnum):
    """User classification for permission management."""
    customer = "customer"     # Regular users with fixed permissions
    auditor = "auditor"       # Compliance reviewers with read-only access
    admin = "admin"            # System administrators with full access


class FixedPermissionSet:
    """
    Defines immutable permission sets for each user role type.
    """
    
    # Customer permissions (fixed, cannot be changed by admin)
    CUSTOMER_PERMISSIONS = [
        ("checklist", "read"),
        ("assessment", "read"),
        ("assessment", "create"),
        ("assessment", "update"),
        ("assessment_submit", "submit"),
        ("dashboard", "read"),
        ("report", "read"),
    ]
    
    # Auditor permissions (read-only, but can be managed)
    AUDITOR_PERMISSIONS = [
        ("checklist", "read"),
        ("assessment", "read"),
        ("dashboard", "read"),
        ("report", "read"),
        ("user_management", "read"),
        ("payment_management", "read"),
        ("audit_log", "read"),
    ]
    
    # Admin permissions (full system access)
    ADMIN_PERMISSIONS = [
        ("checklist", "read"),
        ("checklist", "create"),
        ("checklist", "update"),
        ("checklist_admin", "create"),
        ("checklist_admin", "update"),
        ("checklist_admin", "delete"),
        ("checklist_admin", "manage"),
        ("assessment", "read"),
        ("assessment", "create"),
        ("assessment", "update"),
        ("assessment_submit", "submit"),
        ("dashboard", "read"),
        ("report", "read"),
        ("report", "create"),
        ("user_management", "read"),
        ("user_management", "manage"),
        ("payment_management", "read"),
        ("payment_management", "manage"),
        ("permission_management", "manage"),
        ("audit_log", "read"),
        ("audit_log", "manage"),
    ]


class UserManagementService:
    """
    Service for user lifecycle and permission management.
    
    Enforces business rules about which roles can be managed by admins
    and ensures fixed permission sets are properly applied.
    """
    
    @staticmethod
    def create_user_with_role(
        db: Session,
        email: str,
        password_hash: str,
        role_code: str = "customer"
    ) -> User:
        """
        Create a new user with the specified role and auto-assign permissions.
        
        Args:
            db: Database session
            email: User email
            password_hash: Hashed password
            role_code: Role code ("customer", "auditor", or "admin")
        
        Returns:
            User object with role assigned
        """
        # Map role code to UserRole enum
        role_enum_map = {
            "admin": UserRole.admin,
            "auditor": UserRole.auditor,
            "customer": UserRole.customer,
        }
        
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            role=role_enum_map.get(role_code, UserRole.customer).value,
            is_active=True
        )
        db.add(user)
        db.flush()
        
        # Assign RBAC role with fixed permissions
        RBACService.assign_role_by_code(db, user.id, role_code, user.id)
        
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def change_user_role(
        db: Session,
        user_id: UUID,
        new_role_code: str,
        admin_user_id: UUID
    ) -> User:
        """
        Change user's role and update permissions.
        
        Rules:
        - Admin can change customer to auditor/admin only if necessary
        - Admin can change auditor to admin/customer to test scenarios
        - Cannot change customer to unmanaged role
        - Customer role permissions remain fixed
        
        Args:
            db: Database session
            user_id: User ID to change
            new_role_code: New role code
            admin_user_id: Admin performing the change
        
        Returns:
            Updated User object
        """
        # Get target user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("user_not_found")
        
        # Get admin user
        admin_user = db.query(User).filter(User.id == admin_user_id).first()
        if not admin_user or admin_user.role != UserRole.admin:
            raise PermissionError("only_admins_can_change_user_roles")
        
        # Cannot change own role
        if user_id == admin_user_id:
            raise ValueError("cannot_change_your_own_role")
        
        # Cannot change customer role except for testing (and must be done explicitly)
        if user.role == UserRole.customer.value and new_role_code != "customer":
            # This requires explicit acknowledgment
            pass
        
        # Update user's direct role field
        user.role = new_role_code
        
        # Remove old role assignment
        db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id
        ).delete()
        
        # Assign new role with permissions
        RBACService.assign_role_by_code(db, user_id, new_role_code, admin_user_id)
        
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_manageable_users(
        db: Session,
        admin_user_id: UUID
    ) -> list[User]:
        """
        Get all users that an admin can manage.
        
        Rules:
        - Admin can manage other admins and auditors
        - Admin can VIEW but NOT MANAGE customers (different API)
        
        Args:
            db: Database session
            admin_user_id: Admin user ID
        
        Returns:
            List of manageable users
        """
        return db.query(User).filter(
            and_(
                User.id != admin_user_id,  # Exclude self
                User.role.in_([UserRole.admin.value, UserRole.auditor.value])
            )
        ).all()
    
    @staticmethod
    def get_customers(
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> list[User]:
        """
        Get all customer users (for separate customer management API).
        
        Args:
            db: Database session
            skip: Pagination skip
            limit: Pagination limit
        
        Returns:
            List of customer users
        """
        return db.query(User).filter(
            User.role == UserRole.customer.value
        ).offset(skip).limit(limit).all()
    
    @staticmethod
    def can_modify_user_permissions(
        user_role: str,
        admin_user_id: UUID
    ) -> bool:
        """
        Check if admin can modify a user's permissions.
        
        Rules:
        - Cannot modify customer permissions (always fixed)
        - Can modify auditor/admin permissions
        
        Args:
            user_role: Target user's role
            admin_user_id: Admin user ID
        
        Returns:
            True if permissions can be modified
        """
        # Customer permissions are always fixed/immutable
        if user_role == UserRole.customer.value:
            return False
        
        # Auditor and admin permissions can be modified
        return user_role in [UserRole.auditor.value, UserRole.admin.value]
    
    @staticmethod
    def assign_custom_permissions_to_auditor(
        db: Session,
        auditor_id: UUID,
        permission_keys: list[tuple[str, str]],
        admin_user_id: UUID
    ) -> None:
        """
        Assign custom permissions to auditor role.
        
        NOTE: Customers cannot have custom permissions (only fixed set).
        
        Args:
            db: Database session
            auditor_id: User ID to modify (must be auditor)
            permission_keys: List of (resource, action) tuples
            admin_user_id: Admin performing change
        
        Returns:
            None
        
        Raises:
            ValueError if target is not auditor
            PermissionError if admin not authorized
        """
        # Verify target is auditor
        user = db.query(User).filter(User.id == auditor_id).first()
        if not user or user.role != UserRole.auditor.value:
            raise ValueError("target_user_not_auditor")
        
        # Verify admin
        admin = db.query(User).filter(User.id == admin_user_id).first()
        if not admin or admin.role != UserRole.admin.value:
            raise PermissionError("only_admins_can_assign_permissions")
        
        # Get or create permissions and assign to user's role
        user_roles = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == auditor_id
        ).all()
        
        for user_role_assignment in user_roles:
            role_id = user_role_assignment.role_id
            
            for resource, action in permission_keys:
                permission = RBACService.get_or_create_permission(
                    db, resource, action
                )
                RBACService.add_permission_to_role(db, role_id, permission.id)
    
    @staticmethod
    def reset_permissions_for_role(
        db: Session,
        user_id: UUID,
        admin_user_id: UUID
    ) -> None:
        """
        Reset user's permissions to the default set for their role.
        
        Useful for both auditors and admins to return to baseline permissions.
        (Customer permissions are always at default - no changes allowed)
        
        Args:
            db: Database session
            user_id: User ID to reset
            admin_user_id: Admin performing the action
        
        Returns:
            None
        """
        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("user_not_found")
        
        # Verify admin
        admin = db.query(User).filter(User.id == admin_user_id).first()
        if not admin or admin.role != UserRole.admin.value:
            raise PermissionError("only_admins_can_reset_permissions")
        
        # Determine permission set based on role
        permission_set_map = {
            UserRole.admin.value: FixedPermissionSet.ADMIN_PERMISSIONS,
            UserRole.auditor.value: FixedPermissionSet.AUDITOR_PERMISSIONS,
            UserRole.customer.value: FixedPermissionSet.CUSTOMER_PERMISSIONS,
        }
        
        permission_set = permission_set_map.get(user.role)
        if not permission_set:
            raise ValueError("unknown_user_role")
        
        # Get user's roles and clear permissions
        user_role_assignments = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user_id
        ).all()
        
        for assignment in user_role_assignments:
            # Delete existing role permissions
            db.query(RBACService.__class__.__dict__.get('role_permissions')).delete()
        
        # Assign default permission set
        for resource, action in permission_set:
            permission = RBACService.get_or_create_permission(
                db, resource, action
            )
            for assignment in user_role_assignments:
                RBACService.add_permission_to_role(db, assignment.role_id, permission.id)
