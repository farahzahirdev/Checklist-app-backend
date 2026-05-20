"""merge product and settings migration heads

Revision ID: 20260520_0003_merge_product_and_settings_heads
Revises: 20260519_0002_add_products_checklist_type_id, 20260520_0002_merge_dynamic_settings_heads
Create Date: 2026-05-20 00:20:00.000000
"""


# revision identifiers, used by Alembic.
revision = '20260520_0003_merge_product_and_settings_heads'
down_revision = ('20260519_0002_add_products_checklist_type_id', '20260520_0002_merge_dynamic_settings_heads')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
