"""Audited invoice correction approval metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0008_invoice_correction_review"
down_revision = "0007_ledger_access_opening"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("invoice_revision", sa.Column("replacement", sa.Text()))
    op.add_column("invoice_revision", sa.Column("source_batch_id", sa.Integer(), sa.ForeignKey("import_batch.id")))
    op.add_column("invoice_revision", sa.Column("reason", sa.String(500)))
    op.add_column("invoice_revision", sa.Column("revised_by", sa.String(255)))

def downgrade():
    op.drop_column("invoice_revision", "revised_by")
    op.drop_column("invoice_revision", "reason")
    op.drop_column("invoice_revision", "source_batch_id")
    op.drop_column("invoice_revision", "replacement")