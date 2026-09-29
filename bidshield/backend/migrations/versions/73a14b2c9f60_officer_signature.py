"""Persist a private PNG signature for each officer account."""

from alembic import op
import sqlalchemy as sa


revision = "73a14b2c9f60"
down_revision = "5b1c82b6aa01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("signature_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "signature_data")
