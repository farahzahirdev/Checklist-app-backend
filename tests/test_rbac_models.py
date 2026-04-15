"""
Quick test to verify RBAC models and relationships are correctly configured.
"""
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Test imports
try:
    from app.models import (
        User,
        Permission,
        Role,
        RolePermission,
        UserRoleAssignment,
    )
    from app.models.rbac import PermissionResource, PermissionAction
    from app.db.base import Base
    
    print("✓ All models imported successfully")
    
    # Check relationships exist
    assert hasattr(User, 'user_roles_rel'), "User should have user_roles_rel relationship"
    print("✓ User.user_roles_rel relationship exists")
    
    assert hasattr(Role, 'role_permissions'), "Role should have role_permissions relationship"
    print("✓ Role.role_permissions relationship exists")
    
    assert hasattr(Role, 'user_roles'), "Role should have user_roles relationship"
    print("✓ Role.user_roles relationship exists")
    
    assert hasattr(Permission, 'role_permissions'), "Permission should have role_permissions relationship"
    print("✓ Permission.role_permissions relationship exists")
    
    assert hasattr(UserRoleAssignment, 'user'), "UserRoleAssignment should have user relationship"
    print("✓ UserRoleAssignment.user relationship exists")
    
    assert hasattr(UserRoleAssignment, 'role'), "UserRoleAssignment should have role relationship"
    print("✓ UserRoleAssignment.role relationship exists")
    
    # Check enums
    assert hasattr(PermissionResource, 'checklist'), "PermissionResource should have checklist"
    assert hasattr(PermissionAction, 'read'), "PermissionAction should have read"
    print("✓ Permission enums configured")
    
    # Check table names
    assert UserRoleAssignment.__tablename__ == "user_roles", "UserRoleAssignment should map to user_roles table"
    print("✓ UserRoleAssignment maps to user_roles table")
    
    print("\n✅ All RBAC model relationships verified!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
