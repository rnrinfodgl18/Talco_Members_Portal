"""Add administrator-managed application theme."""
from alembic import op
import sqlalchemy as sa

revision = "0014_custom_theme"
down_revision = "0013_party_alias_binding"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_setting", sa.Column("theme_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("company_setting", "theme_json")
