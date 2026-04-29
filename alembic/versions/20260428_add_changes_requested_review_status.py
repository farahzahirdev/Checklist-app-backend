"""Add changes_requested status to review_status enum

Revision ID: 20260428_add_changes_requested
Revises: 20260414_0004
Create Date: 2026-04-28 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260428_add_changes_requested"
down_revision: Union[str, None] = "2026_04_27_22_45"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Add changes_requested value to review_status enum."""
    # Check if the enum value already exists to avoid errors
    connection = op.get_bind()
    
    # Try to add the new enum value
    try:
        op.execute("ALTER TYPE review_status ADD VALUE 'changes_requested'")
    except Exception as e:
        # If the value already exists, ignore the error
        if "already exists" in str(e) or "duplicate" in str(e).lower():
            pass
        else:
            raise e


def downgrade() -> None:
    """Remove changes_requested value from review_status enum."""
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum type, which is complex
    # For now, we'll leave the enum value in place for backward compatibility
    pass
