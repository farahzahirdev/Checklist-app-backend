"""
RBAC Tests

Comprehensive tests for the Role-Based Access Control system.
"""
import uuid
import pytest
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.rbac import Permission, Role, RolePermission, UserRoleAssignment
from app.services.rbac import RBACService
from app.schemas.auth import UserRoleCode


@pytest.fixture
def admin_user(db: Session) -> User:
    """Create an admin user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        password_hash="hashed_password",
        role=UserRole.admin,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def customer_user(db: Session) -> User:
    """Create a customer user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="customer@test.com",
        password_hash="hashed_password",
        role=UserRole.customer,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def auditor_user(db: Session) -> User:
    """Create an auditor user for testing."""
    user = User(
        id=uuid.uuid4(),
        email="auditor@test.com",
        password_hash="hashed_password",
        role=UserRole.auditor,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_get_system_roles(db: Session):
    """Test retrieving all system roles."""
    roles = RBACService.get_all_system_roles(db)
    assert len(roles) == 3
    role_codes = {role.code for role in roles}
    assert role_codes == {"admin", "auditor", "customer"}


def test_get_role_by_code(db: Session):
    """Test retrieving a role by its code."""
    admin_role = RBACService.get_role_by_code(db, "admin")
    assert admin_role is not None
    assert admin_role.code == "admin"
    assert admin_role.name == "Administrator"
    
    customer_role = RBACService.get_role_by_code(db, "customer")
    assert customer_role is not None
    assert customer_role.code == "customer"


def test_assign_role_to_user(db: Session, customer_user: User):
    """Test assigning a role to a user."""
    admin_role = RBACService.get_role_by_code(db, "admin")
    
    assignment = RBACService.assign_role_to_user(
        db,
        user_id=customer_user.id,
        role_id=admin_role.id,
        assigned_by_user_id=customer_user.id
    )
    
    assert assignment is not None
    assert assignment.user_id == customer_user.id
    assert assignment.role_id == admin_role.id


def test_assign_role_by_code(db: Session, customer_user: User):
    """Test assigning a role to a user by role code."""
    assignment = RBACService.assign_role_by_code(
        db,
        user_id=customer_user.id,
        role_code="admin",
        assigned_by_user_id=customer_user.id
    )
    
    assert assignment is not None
    assert assignment.user_id == customer_user.id
    
    # Get the role that was assigned
    admin_role = RBACService.get_role_by_code(db, "admin")
    assert assignment.role_id == admin_role.id


def test_get_user_roles(db: Session, customer_user: User):
    """Test retrieving all roles assigned to a user."""
    # Initially customer has no RBAC roles (only User.role field)
    roles = RBACService.get_user_roles(db, customer_user.id)
    initial_count = len(roles)
    
    # Assign a role
    RBACService.assign_role_by_code(db, customer_user.id, "customer", customer_user.id)
    
    # Check roles again
    roles = RBACService.get_user_roles(db, customer_user.id)
    assert len(roles) >= initial_count


def test_has_permission_admin(db: Session, admin_user: User):
    """Test that admin user has required permissions."""
    # Assign admin role
    RBACService.assign_role_by_code(db, admin_user.id, "admin", admin_user.id)
    
    # Admin should have permission to manage permissions
    assert RBACService.has_permission(
        db,
        admin_user.id,
        "permission_management",
        "manage"
    )
    
    # Admin should be able to read checklists
    assert RBACService.has_permission(
        db,
        admin_user.id,
        "checklist",
        "read"
    )


def test_has_permission_customer(db: Session, customer_user: User):
    """Test that customer user has appropriate permissions."""
    # Assign customer role
    RBACService.assign_role_by_code(db, customer_user.id, "customer", customer_user.id)
    
    # Customer should be able to read checklists
    assert RBACService.has_permission(
        db,
        customer_user.id,
        "checklist",
        "read"
    )
    
    # Customer should be able to create assessments
    assert RBACService.has_permission(
        db,
        customer_user.id,
        "assessment",
        "create"
    )
    
    # Customer should NOT be able to manage permissions
    assert not RBACService.has_permission(
        db,
        customer_user.id,
        "permission_management",
        "manage"
    )


def test_has_permission_auditor(db: Session, auditor_user: User):
    """Test that auditor user has read-only permissions."""
    # Assign auditor role
    RBACService.assign_role_by_code(db, auditor_user.id, "auditor", auditor_user.id)
    
    # Auditor should be able to read checklists
    assert RBACService.has_permission(
        db,
        auditor_user.id,
        "checklist",
        "read"
    )
    
    # Auditor should be able to read assessments
    assert RBACService.has_permission(
        db,
        auditor_user.id,
        "assessment",
        "read"
    )
    
    # Auditor should NOT be able to create checklists
    assert not RBACService.has_permission(
        db,
        auditor_user.id,
        "checklist",
        "create"
    )
    
    # Auditor should NOT be able to create assessments
    assert not RBACService.has_permission(
        db,
        auditor_user.id,
        "assessment",
        "create"
    )


def test_has_any_permission(db: Session, customer_user: User):
    """Test checking if user has any of multiple permissions."""
    # Assign customer role
    RBACService.assign_role_by_code(db, customer_user.id, "customer", customer_user.id)
    
    # Customer should have at least one of these permissions
    has_any = RBACService.has_any_permission(
        db,
        customer_user.id,
        [
            ("checklist", "read"),
            ("permission_management", "manage"),  # This one customer doesn't have
        ]
    )
    assert has_any
    
    # Customer doesn't have any of these permissions
    has_any = RBACService.has_any_permission(
        db,
        customer_user.id,
        [
            ("permission_management", "manage"),
            ("payment_management", "manage"),
        ]
    )
    assert not has_any


def test_has_all_permissions(db: Session, customer_user: User):
    """Test checking if user has all of multiple permissions."""
    # Assign customer role
    RBACService.assign_role_by_code(db, customer_user.id, "customer", customer_user.id)
    
    # Customer has all of these permissions
    has_all = RBACService.has_all_permissions(
        db,
        customer_user.id,
        [
            ("checklist", "read"),
            ("assessment", "read"),
        ]
    )
    assert has_all
    
    # Customer doesn't have all of these permissions
    has_all = RBACService.has_all_permissions(
        db,
        customer_user.id,
        [
            ("checklist", "read"),
            ("permission_management", "manage"),
        ]
    )
    assert not has_all


def test_remove_role_from_user(db: Session, customer_user: User):
    """Test removing a role from a user."""
    customer_role = RBACService.get_role_by_code(db, "customer")
    
    # Assign role
    RBACService.assign_role_to_user(
        db,
        customer_user.id,
        customer_role.id,
        customer_user.id
    )
    
    # Verify role is assigned
    roles = RBACService.get_user_roles(db, customer_user.id)
    initial_count = len(roles)
    assert initial_count > 0
    
    # Remove role
    removed = RBACService.remove_role_from_user(
        db,
        customer_user.id,
        customer_role.id
    )
    assert removed
    
    # Verify role is removed
    roles = RBACService.get_user_roles(db, customer_user.id)
    assert len(roles) < initial_count


def test_get_or_create_permission(db: Session):
    """Test getting or creating a permission."""
    # Create new permission
    perm = RBACService.get_or_create_permission(
        db,
        resource="test_resource",
        action="test_action",
        description="Test permission"
    )
    
    assert perm.resource == "test_resource"
    assert perm.action == "test_action"
    
    # Get same permission again
    perm2 = RBACService.get_or_create_permission(
        db,
        resource="test_resource",
        action="test_action"
    )
    
    assert perm.id == perm2.id


def test_add_permission_to_role(db: Session):
    """Test adding a permission to a role."""
    admin_role = RBACService.get_role_by_code(db, "admin")
    
    # Create a new permission
    perm = RBACService.get_or_create_permission(
        db,
        resource="test",
        action="new_action",
        description="New test permission"
    )
    
    # Add to role
    assignment = RBACService.add_permission_to_role(db, admin_role.id, perm.id)
    
    assert assignment.role_id == admin_role.id
    assert assignment.permission_id == perm.id


def test_remove_permission_from_role(db: Session):
    """Test removing a permission from a role."""
    admin_role = RBACService.get_role_by_code(db, "admin")
    
    # Get an existing permission assigned to admin
    admin_perms = db.query(RolePermission).filter(
        RolePermission.role_id == admin_role.id
    ).first()
    
    if admin_perms:
        # Remove permission
        removed = RBACService.remove_permission_from_role(
            db,
            admin_role.id,
            admin_perms.permission_id
        )
        assert removed


def test_get_user_permissions(db: Session, admin_user: User):
    """Test getting all permissions for a user."""
    # Assign admin role
    RBACService.assign_role_by_code(db, admin_user.id, "admin", admin_user.id)
    
    # Get permissions
    permissions = RBACService.get_user_permissions(db, admin_user.id)
    
    # Admin should have many permissions
    assert len(permissions) > 0
    
    # Verify some expected permissions exist
    perm_keys = {f"{p.resource}:{p.action}" for p in permissions}
    assert "checklist:read" in perm_keys
    assert "permission_management:manage" in perm_keys


def test_inactive_user_no_permissions(db: Session, customer_user: User):
    """Test that inactive users have no permissions."""
    # Assign a role
    RBACService.assign_role_by_code(db, customer_user.id, "customer", customer_user.id)
    
    # Deactivate user
    customer_user.is_active = False
    db.commit()
    
    # Inactive user should have no permissions
    assert not RBACService.has_permission(
        db,
        customer_user.id,
        "checklist",
        "read"
    )
