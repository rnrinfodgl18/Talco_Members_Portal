"""Store the tannery selected for each Tally ledger alias."""
from alembic import op
import sqlalchemy as sa

revision = "0013_party_alias_binding"
down_revision = "0012_dashboard_pwa_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("party_alias", sa.Column("tannery_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_party_alias_tannery", "party_alias", "tannery",
                          ["tannery_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_party_alias_tannery_id", "party_alias", ["tannery_id"])
    op.execute("""
        UPDATE party_alias AS pa
        SET tannery_id = links.tannery_id
        FROM (
            SELECT party_id, MIN(tannery_id) AS tannery_id
            FROM tannery_party_link
            WHERE valid_to IS NULL
            GROUP BY party_id
            HAVING COUNT(DISTINCT tannery_id) = 1
        ) AS links
        WHERE pa.party_id = links.party_id
    """)


def downgrade():
    op.drop_index("ix_party_alias_tannery_id", table_name="party_alias")
    op.drop_constraint("fk_party_alias_tannery", "party_alias", type_="foreignkey")
    op.drop_column("party_alias", "tannery_id")
