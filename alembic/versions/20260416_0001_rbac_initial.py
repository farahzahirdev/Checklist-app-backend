"""Create RBAC tables and populate initial permissions and roles.

Revision ID: 20260416_0001_rbac_initial
Revises: 20260415_0014
Create Date: 2026-04-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text
import uuid

# revision identifiers, used by Alembic.
revision = '20260416_0001_rbac_initial'
down_revision = '20260415_0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create permissions table
    op.create_table(
        'permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource', sa.String(50), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('description', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource', 'action', name='uq_permissions_resource_action')
    )
    op.create_index(op.f('ix_permissions_resource'), 'permissions', ['resource'])
    
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(50), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_system_role', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_roles_code')
    )
    op.create_index(op.f('ix_roles_code'), 'roles', ['code'])
    
    # Create role_permissions join table
    op.create_table(
        'role_permissions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('permission_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permissions')
    )
    
    # Create user_roles join table
    op.create_table(
        'user_roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['assigned_by'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_user_roles')
    )

    # Populate initial permissions
    connection = op.get_bind()
    
    # Define all permissions
    permissions = [
        # Checklist permissions
        ('checklist', 'read', 'Read checklists'),
        ('checklist', 'create', 'Create checklists'),
        ('checklist', 'update', 'Update checklists'),
        ('checklist', 'delete', 'Delete checklists'),
        
        ('checklist_admin', 'create', 'Create and manage checklists (admin only)'),
        ('checklist_admin', 'update', 'Update checklist content (admin only)'),
        ('checklist_admin', 'delete', 'Delete checklists (admin only)'),
        ('checklist_admin', 'manage', 'Full checklist administration'),
        
        # Assessment permissions
        ('assessment', 'read', 'Read own assessments'),
        ('assessment', 'create', 'Create new assessments'),
        ('assessment', 'update', 'Update own assessments'),
        ('assessment', 'delete', 'Delete assessments'),
        
        ('assessment_submit', 'submit', 'Submit assessment responses'),
        
        # Report and Dashboard
        ('dashboard', 'read', 'Access dashboard'),
        ('report', 'read', 'Read reports'),
        ('report', 'create', 'Generate reports'),
        ('report', 'update', 'Update reports'),
        ('report', 'delete', 'Delete reports'),
        
        # User and admin permissions
        ('user_management', 'read', 'View user information'),
        ('user_management', 'create', 'Create users'),
        ('user_management', 'update', 'Update user information'),
        ('user_management', 'delete', 'Delete users'),
        ('user_management', 'manage', 'Manage users (admin only)'),
        
        ('payment', 'read', 'View payment information'),
        ('payment', 'manage', 'Manage payments'),
        
        ('permission_management', 'read', 'View permissions'),
        ('permission_management', 'manage', 'Manage permissions and roles (admin only)'),
        
        ('audit_log', 'read', 'View audit logs'),
        ('audit_log', 'manage', 'Manage audit logs (admin only)'),
    ]
    
    permission_ids = {}
    for resource, action, description in permissions:
        perm_id = str(uuid.uuid4())
        connection.execute(
            text(
                """
                INSERT INTO permissions (id, resource, action, description, is_active)
                VALUES (:id, :resource, :action, :description, true)
                """
            ),
            {
                'id': perm_id,
                'resource': resource,
                'action': action,
                'description': description,
            }
        )
        permission_ids[f"{resource}:{action}"] = perm_id
    
    # Create system roles
    admin_role_id = str(uuid.uuid4())
    auditor_role_id = str(uuid.uuid4())
    customer_role_id = str(uuid.uuid4())
    
    connection.execute(
        text(
            """
            INSERT INTO roles (id, code, name, description, is_system_role, is_active)
            VALUES
                (:admin_id, 'admin', 'Administrator', 'Full system access', true, true),
                (:auditor_id, 'auditor', 'Auditor', 'Read-only access to audit data', true, true),
                (:customer_id, 'customer', 'Customer', 'Standard customer access', true, true)
            """
        ),
        {
            'admin_id': admin_role_id,
            'auditor_id': auditor_role_id,
            'customer_id': customer_role_id,
        }
    )
    
    # Assign permissions to admin role (all permissions)
    for resource, action, _ in permissions:
        perm_id = permission_ids[f"{resource}:{action}"]
        connection.execute(
            text(
                """
                INSERT INTO role_permissions (id, role_id, permission_id)
                VALUES (:id, :role_id, :permission_id)
                """
            ),
            {
                'id': str(uuid.uuid4()),
                'role_id': admin_role_id,
                'permission_id': perm_id,
            }
        )
    
    # Assign permissions to auditor role (read-only permissions)
    auditor_perms = [
        ('checklist', 'read'),
        ('assessment', 'read'),
        ('dashboard', 'read'),
        ('report', 'read'),
        ('user_management', 'read'),
        ('payment', 'read'),
        ('audit_log', 'read'),
    ]
    for resource, action in auditor_perms:
        perm_id = permission_ids[f"{resource}:{action}"]
        connection.execute(
            text(
                """
                INSERT INTO role_permissions (id, role_id, permission_id)
                VALUES (:id, :role_id, :permission_id)
                """
            ),
            {
                'id': str(uuid.uuid4()),
                'role_id': auditor_role_id,
                'permission_id': perm_id,
            }
        )
    
    # Assign permissions to customer role (customer-specific permissions)
    customer_perms = [
        ('checklist', 'read'),
        ('assessment', 'read'),
        ('assessment', 'create'),
        ('assessment', 'update'),
        ('assessment_submit', 'submit'),
        ('dashboard', 'read'),
        ('report', 'read'),
    ]
    for resource, action in customer_perms:
        perm_id = permission_ids[f"{resource}:{action}"]
        connection.execute(
            text(
                """
                INSERT INTO role_permissions (id, role_id, permission_id)
                VALUES (:id, :role_id, :permission_id)
                """
            ),
            {
                'id': str(uuid.uuid4()),
                'role_id': customer_role_id,
                'permission_id': perm_id,
            }
        )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_table('roles')
    op.drop_table('permissions')
