"""Add optional username login."""
from alembic import op
import sqlalchemy as sa
revision = "0016_user_username"
down_revision = "0015_whatsapp_verification"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("app_user", sa.Column("username", sa.String(80), nullable=True))
    op.create_unique_constraint("uq_app_user_username", "app_user", ["username"])
def downgrade():
    op.drop_constraint("uq_app_user_username", "app_user", type_="unique")
    op.drop_column("app_user", "username")
