"""Update audit action enum with all new actions

Revision ID: 2026_04_27_22_45
Revises: 2026_04_27_22_30
Create Date: 2026-04-27 22:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2026_04_27_22_45'
down_revision: Union[str, None] = '2026_04_27_22_30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to the existing enum
    new_values = [
        'auth_password_change',
        'auth_profile_update',
        'user_create',
        'user_update',
        'user_delete',
        'user_status_change',
        'checklist_delete',
        'checklist_archive',
        'checklist_version_update',
        'assessment_create',
        'assessment_update',
        'assessment_delete',
        'assessment_withdraw',
        'assessment_extend',
        'assessment_archive',
        'assessment_answer_create',
        'assessment_answer_update',
        'assessment_answer_delete',
        'assessment_review_create',
        'assessment_review_update',
        'assessment_review_submit',
        'assessment_review_approve',
        'assessment_review_reject',
        'answer_review_create',
        'answer_review_update',
        'answer_review_delete',
        'report_create',
        'report_update',
        'report_delete',
        'report_reject',
        'report_changes_request',
        'payment_create',
        'payment_update',
        'payment_complete',
        'payment_refund',
        'payment_fail',
        'media_upload',
        'media_update',
        'media_delete',
        'media_download',
        'system_backup',
        'system_restore',
        'system_maintenance',
        'system_config_update',
        'role_create',
        'role_update',
        'role_delete',
        'permission_create',
        'permission_update',
        'permission_delete',
        'role_permission_assign',
        'role_permission_revoke'
    ]
    
    # Add each new value to the enum
    for value in new_values:
        try:
            op.execute(f"ALTER TYPE audit_action ADD VALUE '{value}'")
        except Exception:
            # Value might already exist, skip
            pass


def downgrade() -> None:
    # For downgrade, we'll recreate the original enum
    op.execute("DROP TYPE IF EXISTS audit_action")
    
    op.execute("""
        CREATE TYPE audit_action AS ENUM (
            'auth_login',
            'auth_logout',
            'auth_mfa_verify',
            'checklist_create',
            'checklist_update',
            'checklist_publish',
            'assessment_submit',
            'report_approve',
            'report_publish',
            'user_role_change'
        )
    """)
