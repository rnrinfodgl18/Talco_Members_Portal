"""Allocate serial numbers automatically without changing existing masters."""
from alembic import op
import sqlalchemy as sa

revision = '0006_auto_tannery_serial'
down_revision = '0005_pump_master'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tannery_serial_counter',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('last_value', sa.Integer(), nullable=False))
    op.execute('INSERT INTO tannery_serial_counter (id, last_value) SELECT 1, COALESCE(MAX(sno), 0) FROM tannery')


def downgrade():
    op.drop_table('tannery_serial_counter')
