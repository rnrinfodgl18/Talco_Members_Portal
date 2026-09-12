"""Introduce Pump Master and preserve existing tannery assignments."""
from alembic import op
import sqlalchemy as sa

revision = '0005_pump_master'
down_revision = '0004_phase5_auth'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('pump',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('location', sa.String(255)),
        sa.Column('notes', sa.Text()))
    op.execute("""INSERT INTO pump (code, name)
        SELECT code, 'Pump house ' || code FROM (
            SELECT DISTINCT pump_house AS code FROM tannery
            UNION SELECT unnest(ARRAY['A','B','C','D','E'])
        ) existing_codes ORDER BY code""")
    op.alter_column('tannery', 'pump_house', existing_type=sa.String(1), type_=sa.String(20), existing_nullable=False)
    op.create_foreign_key('fk_tannery_pump_house', 'tannery', 'pump', ['pump_house'], ['code'],
                          onupdate='CASCADE', ondelete='RESTRICT')


def downgrade():
    # Refuse truncation of codes introduced after this migration.
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM tannery WHERE length(pump_house) > 1')):
        raise RuntimeError('Reassign tanneries with multi-character pump codes before downgrade')
    op.drop_constraint('fk_tannery_pump_house', 'tannery', type_='foreignkey')
    op.alter_column('tannery', 'pump_house', existing_type=sa.String(20), type_=sa.String(1), existing_nullable=False)
    op.drop_table('pump')
