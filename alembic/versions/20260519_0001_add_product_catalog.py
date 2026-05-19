"""Add product catalogue tables.

Revision ID: 20260519_0001_add_product_catalog
Revises: 20260518_0001_add_report_pdf_password_encrypted
Create Date: 2026-05-19 00:01:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260519_0001_add_product_catalog"
down_revision: Union[str, None] = "20260518_0001_add_report_pdf_password_encrypted"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_product_categories_code"),
    )
    op.create_index(op.f("ix_product_categories_code"), "product_categories", ["code"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_product_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("checklist_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("checklist_type_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_kind", sa.String(length=40), nullable=False, server_default="documentation"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("brochure_pdf_url", sa.String(length=500), nullable=True),
        sa.Column("hero_image_url", sa.String(length=500), nullable=True),
        sa.Column("external_url", sa.String(length=500), nullable=True),
        sa.Column("cta_label", sa.String(length=120), nullable=True),
        sa.Column("stripe_product_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["product_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["parent_product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["checklist_id"], ["checklists.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checklist_type_id"], ["checklist_types.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
        sa.UniqueConstraint("checklist_id", name="uq_products_checklist_id"),
    )
    op.create_index(op.f("ix_products_checklist_id"), "products", ["checklist_id"], unique=False)
    op.create_index(op.f("ix_products_checklist_type_id"), "products", ["checklist_type_id"], unique=False)
    op.create_index(op.f("ix_products_stripe_product_id"), "products", ["stripe_product_id"], unique=False)

    op.execute(
        """
        UPDATE products AS p
        SET checklist_type_id = c.checklist_type_id
        FROM checklists AS c
        WHERE p.checklist_id = c.id
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_products_stripe_product_id"), table_name="products")
    op.drop_index(op.f("ix_products_checklist_type_id"), table_name="products")
    op.drop_index(op.f("ix_products_checklist_id"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_product_categories_code"), table_name="product_categories")
    op.drop_table("product_categories")