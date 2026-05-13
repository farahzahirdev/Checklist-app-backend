#!/usr/bin/env python3
"""
Fix admin@example.com user - restore admin role and ensure proper role assignments.
"""
import os
import sys
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Load environment variables
load_dotenv()

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.user import User, UserRole
from app.models.rbac import UserRoleAssignment, Role
from app.db.session import get_db_url

def fix_admin_user():
    """
    Fix admin@example.com user:
    1. Find the user
    2. Set role to "admin"
    3. Remove all role assignments
    4. Assign admin role from RBAC
    5. Verify the fix
    """
    
    # Create database session
    engine = create_engine(get_db_url())
    
    with Session(engine) as db:
        print("=" * 80)
        print("FIX ADMIN@EXAMPLE.COM USER")
        print("=" * 80)
        
        # Step 1: Find the user
        print("\n[1/5] Finding admin@example.com user...")
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        
        if not user:
            print("❌ User not found!")
            return False
        
        print(f"✅ Found user: {user.id}")
        print(f"   Current role: {user.role}")
        print(f"   Email: {user.email}")
        print(f"   Is active: {user.is_active}")
        
        # Step 2: Set role to "admin"
        print("\n[2/5] Setting role to 'admin'...")
        user.role = UserRole.admin.value
        db.flush()
        print(f"✅ Role set to: {user.role}")
        
        # Step 3: Remove all role assignments
        print("\n[3/5] Removing existing role assignments...")
        existing_assignments = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user.id
        ).all()
        print(f"   Found {len(existing_assignments)} existing assignments")
        for assignment in existing_assignments:
            db.delete(assignment)
        db.flush()
        print(f"✅ Removed all role assignments")
        
        # Step 4: Assign admin role from RBAC
        print("\n[4/5] Assigning admin role from RBAC...")
        admin_role = db.scalar(select(Role).where(Role.code == "admin"))
        
        if not admin_role:
            print("❌ Admin role not found in database!")
            print("   You may need to run: python fix_admin_permissions.py first")
            db.rollback()
            return False
        
        print(f"✅ Found admin role: {admin_role.id}")
        
        # Create new role assignment
        new_assignment = UserRoleAssignment(
            user_id=user.id,
            role_id=admin_role.id,
            assigned_by_user_id=user.id  # Self-assigned
        )
        db.add(new_assignment)
        db.commit()
        print(f"✅ Assigned admin role to user")
        
        # Step 5: Verify the fix
        print("\n[5/5] Verifying the fix...")
        db.refresh(user)
        
        assignments = db.query(UserRoleAssignment).filter(
            UserRoleAssignment.user_id == user.id
        ).all()
        
        print(f"✅ User role: {user.role}")
        print(f"✅ Role assignments: {len(assignments)}")
        for assignment in assignments:
            role = db.get(Role, assignment.role_id)
            print(f"   - {role.code} (ID: {role.id})")
        
        print("\n" + "=" * 80)
        print("✅ ADMIN USER FIX COMPLETE")
        print("=" * 80)
        print("\nUser is now restored to admin with full permissions.")
        print("You can log in and verify the role is correct.")
        
        return True


if __name__ == "__main__":
    try:
        success = fix_admin_user()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
