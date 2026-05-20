"""merge dynamic settings migration heads

Revision ID: 20260520_0002_merge_dynamic_settings_heads
Revises: 20260420_0001_remove_checklist_type_version_unique, 20260427_0002_merge_auditor_permissions, 20260520_0001_system_settings_dynamic_config
Create Date: 2026-05-20 00:10:00.000000
"""


# revision identifiers, used by Alembic.
revision = '20260520_0002_merge_dynamic_settings_heads'
down_revision = ('20260420_0001_remove_checklist_type_version_unique', '20260427_0002_merge_auditor_permissions', '20260520_0001_system_settings_dynamic_config')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
