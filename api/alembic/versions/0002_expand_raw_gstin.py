"""Preserve raw master GST cell values without truncation."""

from alembic import op
import sqlalchemy as sa


revision = "0002_expand_raw_gstin"
down_revision = "3254d1133265"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tannery", "gstin", existing_type=sa.String(length=20), type_=sa.String(length=50))


def downgrade() -> None:
    op.alter_column("tannery", "gstin", existing_type=sa.String(length=50), type_=sa.String(length=20))

