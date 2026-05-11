#!/usr/bin/env python3
"""
Script to fix admin user permissions for CMS access.
This ensures admin user has proper role assignments and permissions.
"""

import sys
import os
from uuid import uuid4

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.session import engine
from app.models.rbac import Role, Permission, RolePermission, UserRoleAssignment, PermissionResource, PermissionAction
from app.models.user import User

def fix_admin_permissions():
    """Ensure admin user has all necessary permissions."""
    
    with Session(engine) as db:
        # Get or create admin role
        admin_role = db.query(Role).filter(Role.code == "admin").first()
        if not admin_role:
            print("Creating admin role...")
            admin_role = Role(
                id=uuid4(),
                code="admin",
                name="Administrator",
                description="Full system access",
                is_system_role=True,
                is_active=True
            )
            db.add(admin_role)
            db.flush()
        else:
            print(f"Found admin role: {admin_role}")
        
        # Ensure all permissions exist
        required_permissions = []
        
        # Add CMS-specific permissions
        cms_resources = [
            PermissionResource.checklist_admin,
            PermissionResource.user_management,
            PermissionResource.permission_management,
            PermissionResource.audit_log
        ]
        
        for resource in cms_resources:
            for action in [PermissionAction.create, PermissionAction.read, PermissionAction.update, PermissionAction.delete, PermissionAction.manage]:
                permission = db.query(Permission).filter(
                    Permission.resource == resource.value,
                    Permission.action == action.value
                ).first()
                
                if not permission:
                    print(f"Creating permission: {resource.value}:{action.value}")
                    permission = Permission(
                        id=uuid4(),
                        resource=resource.value,
                        action=action.value,
                        description=f"{action.value} {resource.value}",
                        is_active=True
                    )
                    db.add(permission)
                    db.flush()
                
                required_permissions.append((admin_role.id, permission.id))
        
        # Assign all permissions to admin role
        for role_id, permission_id in required_permissions:
            existing = db.query(RolePermission).filter(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id
            ).first()
            
            if not existing:
                print(f"Assigning permission to admin role")
                role_perm = RolePermission(
                    id=uuid4(),
                    role_id=role_id,
                    permission_id=permission_id
                )
                db.add(role_perm)
        
        # Get admin user and assign role
        admin_user = db.query(User).filter(User.email == "admin@example.com").first()
        if not admin_user:
            # Try to find any admin user
            admin_user = db.query(User).filter(User.role == "admin").first()
            
        if admin_user:
            print(f"Found admin user: {admin_user.email}")
            
            # Check if user has admin role assigned
            existing_assignment = db.query(UserRoleAssignment).filter(
                UserRoleAssignment.user_id == admin_user.id,
                UserRoleAssignment.role_id == admin_role.id
            ).first()
            
            if not existing_assignment:
                print("Assigning admin role to user")
                assignment = UserRoleAssignment(
                    id=uuid4(),
                    user_id=admin_user.id,
                    role_id=admin_role.id,
                    assigned_by=admin_user.id
                )
                db.add(assignment)
            else:
                print("User already has admin role assigned")
        else:
            print("No admin user found!")
        
        db.commit()
        print("Admin permissions fixed successfully!")

if __name__ == "__main__":
    fix_admin_permissions()
