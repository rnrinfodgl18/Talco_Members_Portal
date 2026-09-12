"""Full Tally voucher identity, cancellation state, and receipt allocations."""
from alembic import op
import sqlalchemy as sa

revision = "0009_complete_tally_import"
down_revision = "0008_invoice_correction_review"
branch_labels = None
depends_on = None

def upgrade():
    for table in ("invoice", "receipt"):
        op.add_column(table, sa.Column("source_guid", sa.String(100)))
        op.add_column(table, sa.Column("source_alter_id", sa.Integer()))
        op.add_column(table, sa.Column("is_cancelled", sa.Boolean(), server_default=sa.false(), nullable=False))
        op.create_unique_constraint(f"uq_{table}_source_guid", table, ["source_guid"])
    op.create_table("receipt_allocation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("receipt_id", sa.Integer(), sa.ForeignKey("receipt.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("invoice.id")),
        sa.Column("bill_ref", sa.String(100), nullable=False),
        sa.Column("allocation_type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.UniqueConstraint("receipt_id", "bill_ref", "allocation_type"))

def downgrade():
    op.drop_table("receipt_allocation")
    for table in ("receipt", "invoice"):
        op.drop_constraint(f"uq_{table}_source_guid", table, type_="unique")
        op.drop_column(table, "is_cancelled")
        op.drop_column(table, "source_alter_id")
        op.drop_column(table, "source_guid")
