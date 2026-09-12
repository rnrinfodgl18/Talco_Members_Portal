"""Opening amounts and explicit multi-ledger login access."""
from alembic import op
import sqlalchemy as sa

revision = '0007_ledger_access_opening'
down_revision = '0006_auto_tannery_serial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('party', sa.Column('opening_amount', sa.Numeric(14, 2), server_default='0', nullable=False))
    op.add_column('party', sa.Column('opening_date', sa.Date()))
    op.add_column('party', sa.Column('opening_note', sa.String(500)))
    op.add_column('app_user', sa.Column('ledger_access_configured', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_table('user_ledger_access',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('app_user.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('party_id', sa.Integer(), sa.ForeignKey('party.id', ondelete='RESTRICT'), primary_key=True),
        sa.Column('relationship_role', sa.String(20), nullable=False))
    op.create_check_constraint('ck_user_ledger_relationship', 'user_ledger_access',
        "relationship_role IN ('owner','lessee','account_holder','staff')")


def downgrade():
    op.drop_table('user_ledger_access')
    op.drop_column('app_user', 'ledger_access_configured')
    op.drop_column('party', 'opening_note')
    op.drop_column('party', 'opening_date')
    op.drop_column('party', 'opening_amount')
