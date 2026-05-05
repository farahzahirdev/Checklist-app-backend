"""Add multi-company support: companies, user_company_assignments, and user profile fields

Revision ID: 20260505_0001_multi_company_support
Revises: e1fc5775ab6e
Create Date: 2026-05-05 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260505_0001_multi_company_support"
down_revision = "e1fc5775ab6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create companies table first (no dependencies)
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("website", sa.String(length=500), nullable=True),
        sa.Column("region", sa.String(length=100), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("industry", sa.String(length=50), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("compliance_framework", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_slug", "companies", ["slug"], unique=True)
    op.create_index("ix_companies_name", "companies", ["name"], unique=False)

    # Add new columns to users table
    op.add_column(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("username", sa.String(length=100), nullable=True, unique=True)
    )
    op.add_column(
        "users",
        sa.Column("primary_company_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("job_title", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "users",
        sa.Column("department", sa.String(length=255), nullable=True)
    )
    
    # Create unique index on username
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # Create user_company_assignments table
    op.create_table(
        "user_company_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="staff"),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("department", sa.String(length=255), nullable=True),
        sa.Column("context_notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company_unique"),
    )
    op.create_index("ix_user_company_assignments_user_id", "user_company_assignments", ["user_id"], unique=False)
    op.create_index("ix_user_company_assignments_company_id", "user_company_assignments", ["company_id"], unique=False)
    op.create_index("ix_user_company_assignments_role", "user_company_assignments", ["role"], unique=False)


def downgrade() -> None:
    # Drop user_company_assignments table
    op.drop_index("ix_user_company_assignments_role", table_name="user_company_assignments")
    op.drop_index("ix_user_company_assignments_company_id", table_name="user_company_assignments")
    op.drop_index("ix_user_company_assignments_user_id", table_name="user_company_assignments")
    op.drop_table("user_company_assignments")

    # Drop columns from users table
    op.drop_index("ix_users_username", table_name="users")
    op.drop_column("users", "department")
    op.drop_column("users", "job_title")
    op.drop_column("users", "primary_company_id")
    op.drop_column("users", "username")
    op.drop_column("users", "full_name")

    # Drop companies table
    op.drop_index("ix_companies_name", table_name="companies")
    op.drop_index("ix_companies_slug", table_name="companies")
    op.drop_table("companies")
