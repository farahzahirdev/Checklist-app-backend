"""Add auditor view permissions for admin APIs

Revision ID: 20260427_0001_add_auditor_admin_view_permissions
Revises: 970e0b8e97af
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text
import uuid

# revision identifiers, used by Alembic.
revision = '20260427_0001_add_auditor_admin_view_permissions'
down_revision = '20260416_0001_rbac_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add admin API view permissions for auditor role."""
    connection = op.get_bind()
    
    # Add new permissions for admin API viewing
    admin_view_permissions = [
        ('permission_management', 'read', 'View permissions and roles'),
        ('user_management', 'read', 'View user management information'),
        ('payment_management', 'read', 'View payment management information'),
        ('audit_log', 'read', 'View audit logs'),
    ]
    
    permission_ids = {}
    for resource, action, description in admin_view_permissions:
        # Check if permission already exists
        result = connection.execute(
            text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
            {'resource': resource, 'action': action}
        ).fetchone()
        
        if result:
            permission_ids[f"{resource}:{action}"] = str(result[0])
        else:
            # Create new permission
            perm_id = str(uuid.uuid4())
            connection.execute(
                text("""
                    INSERT INTO permissions (id, resource, action, description, is_active)
                    VALUES (:id, :resource, :action, :description, true)
                """),
                {
                    'id': perm_id,
                    'resource': resource,
                    'action': action,
                    'description': description,
                }
            )
            permission_ids[f"{resource}:{action}"] = perm_id
    
    # Get auditor role ID
    auditor_role_result = connection.execute(
        text("SELECT id FROM roles WHERE code = 'auditor' AND is_active = true")
    ).fetchone()
    
    if auditor_role_result:
        auditor_role_id = str(auditor_role_result[0])
        
        # Add view permissions to auditor role
        for resource, action, _ in admin_view_permissions:
            perm_id = permission_ids[f"{resource}:{action}"]
            
            # Check if assignment already exists
            existing = connection.execute(
                text("""
                    SELECT id FROM role_permissions 
                    WHERE role_id = :role_id AND permission_id = :permission_id
                """),
                {'role_id': auditor_role_id, 'permission_id': perm_id}
            ).fetchone()
            
            if not existing:
                connection.execute(
                    text("""
                        INSERT INTO role_permissions (id, role_id, permission_id)
                        VALUES (:id, :role_id, :permission_id)
                    """),
                    {
                        'id': str(uuid.uuid4()),
                        'role_id': auditor_role_id,
                        'permission_id': perm_id,
                    }
                )


def downgrade() -> None:
    """Remove auditor admin view permissions."""
    connection = op.get_bind()
    
    # Get auditor role ID
    auditor_role_result = connection.execute(
        text("SELECT id FROM roles WHERE code = 'auditor' AND is_active = true")
    ).fetchone()
    
    if auditor_role_result:
        auditor_role_id = str(auditor_role_result[0])
        
        # Remove admin view permissions from auditor role
        admin_view_perms = [
            ('permission_management', 'read'),
            ('user_management', 'read'),
            ('payment_management', 'read'),
            ('audit_log', 'read'),
        ]
        
        for resource, action in admin_view_perms:
            # Get permission ID
            perm_result = connection.execute(
                text("SELECT id FROM permissions WHERE resource = :resource AND action = :action"),
                {'resource': resource, 'action': action}
            ).fetchone()
            
            if perm_result:
                perm_id = str(perm_result[0])
                
                # Remove role permission assignment
                connection.execute(
                    text("""
                        DELETE FROM role_permissions 
                        WHERE role_id = :role_id AND permission_id = :permission_id
                    """),
                    {'role_id': auditor_role_id, 'permission_id': perm_id}
                )
