"""Use canonical GSTIN width after extracting labels and notes."""

from alembic import op
import sqlalchemy as sa


revision = "0003_normalized_gstin_width"
down_revision = "0002_expand_raw_gstin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("tannery", "gstin", existing_type=sa.String(length=50), type_=sa.String(length=20))


def downgrade() -> None:
    op.alter_column("tannery", "gstin", existing_type=sa.String(length=20), type_=sa.String(length=50))

