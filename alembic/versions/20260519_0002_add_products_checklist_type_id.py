"""Add checklist_type_id to products.

Revision ID: 20260519_0002_add_products_checklist_type_id
Revises: 20260519_0001_add_product_catalog
Create Date: 2026-05-19 01:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260519_0002_add_products_checklist_type_id"
down_revision: Union[str, None] = "20260519_0001_add_product_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    product_columns = {col["name"] for col in inspector.get_columns("products")}
    if "checklist_type_id" not in product_columns:
        op.add_column("products", sa.Column("checklist_type_id", postgresql.UUID(as_uuid=True), nullable=True))

    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("products")}
    fk_name = "fk_products_checklist_type_id_checklist_types"
    if fk_name not in fk_names:
        op.create_foreign_key(
            fk_name,
            "products",
            "checklist_types",
            ["checklist_type_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    index_names = {idx.get("name") for idx in inspector.get_indexes("products")}
    idx_name = op.f("ix_products_checklist_type_id")
    if idx_name not in index_names:
        op.create_index(idx_name, "products", ["checklist_type_id"], unique=False)

    op.execute(
        """
        UPDATE products AS p
        SET checklist_type_id = c.checklist_type_id
        FROM checklists AS c
        WHERE p.checklist_id = c.id
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    idx_name = op.f("ix_products_checklist_type_id")
    index_names = {idx.get("name") for idx in inspector.get_indexes("products")}
    if idx_name in index_names:
        op.drop_index(idx_name, table_name="products")

    fk_name = "fk_products_checklist_type_id_checklist_types"
    fk_names = {fk.get("name") for fk in inspector.get_foreign_keys("products")}
    if fk_name in fk_names:
        op.drop_constraint(fk_name, "products", type_="foreignkey")

    product_columns = {col["name"] for col in inspector.get_columns("products")}
    if "checklist_type_id" in product_columns:
        op.drop_column("products", "checklist_type_id")
