"""add_cms_models

Revision ID: 8eee78d32ee3
Revises: 20260505_0005_widen_company_country
Create Date: 2026-05-11 16:17:38.445309
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '8eee78d32ee3'
down_revision = '20260505_0005_widen_company_country'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create cms_pages table
    op.create_table(
        'cms_pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('meta_description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('content_type', sa.String(length=50), nullable=False, server_default='standard'),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('updated_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', 'language', name='uq_cms_pages_slug_language')
    )
    op.create_index('ix_cms_pages_slug', 'cms_pages', ['slug'], unique=False)
    op.create_index('ix_cms_pages_language', 'cms_pages', ['language'], unique=False)

    # Create cms_page_sections table
    op.create_table(
        'cms_page_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('section_type', sa.String(length=50), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['page_id'], ['cms_pages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cms_page_sections_page_id', 'cms_page_sections', ['page_id'], unique=False)

    # Create cms_images table
    op.create_table(
        'cms_images',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False, unique=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('alt_text', sa.Text(), nullable=True),
        sa.Column('uploaded_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('used_in_pages', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cms_images_file_path', 'cms_images', ['file_path'], unique=True)
    op.create_index('ix_cms_images_uploaded_by_id', 'cms_images', ['uploaded_by_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_cms_images_uploaded_by_id', table_name='cms_images')
    op.drop_index('ix_cms_images_file_path', table_name='cms_images')
    op.drop_table('cms_images')
    op.drop_index('ix_cms_page_sections_page_id', table_name='cms_page_sections')
    op.drop_table('cms_page_sections')
    op.drop_index('ix_cms_pages_language', table_name='cms_pages')
    op.drop_index('ix_cms_pages_slug', table_name='cms_pages')
    op.drop_table('cms_pages')
