"""Layer 2 — security_events and login_attempts tables

Revision ID: a7f3d9c21b54
Revises: 73a14b2c9f60
Create Date: 2026-09-30
"""
from alembic import op
import sqlalchemy as sa

revision = "a7f3d9c21b54"
down_revision = "73a14b2c9f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=50), nullable=False, index=True),
        sa.Column("source_ip", sa.String(length=64), index=True),
        sa.Column("username", sa.String(length=100), index=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), index=True),
    )
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=100), nullable=False, index=True),
        sa.Column("source_ip", sa.String(length=64)),
        sa.Column("successful", sa.Boolean(), index=True),
        sa.Column("created_at", sa.DateTime(), index=True),
    )


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("security_events")
