"""add section_category to cms sections

Revision ID: 20260602_add_section_category
Revises: 
Create Date: 2026-06-02 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260602_add_section_category'
down_revision = '20260525_0003'
branch_labels = None
depends_on = None


def upgrade():
    # Add section_category column to cms_page_sections table
    op.add_column('cms_page_sections', sa.Column('section_category', sa.String(length=20), nullable=False, server_default='body'))
    
    # Update existing sections based on their section_type
    # Header sections
    op.execute("""
        UPDATE cms_page_sections 
        SET section_category = 'header' 
        WHERE section_type IN ('hero', 'product_hero')
    """)
    
    # Footer sections  
    op.execute("""
        UPDATE cms_page_sections 
        SET section_category = 'footer' 
        WHERE section_type = 'footer'
    """)
    
    # All others remain as 'body' (default)


def downgrade():
    # Remove the section_category column
    op.drop_column('cms_page_sections', 'section_category')
