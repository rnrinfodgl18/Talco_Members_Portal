"""Per-channel switches for circular delivery."""
from alembic import op
import sqlalchemy as sa
revision = "0019_notification_channels"
down_revision = "0018_optional_user_email"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("company_setting", sa.Column("circular_email_enabled", sa.Boolean(),
        nullable=False, server_default=sa.true()))
    op.add_column("company_setting", sa.Column("circular_whatsapp_enabled", sa.Boolean(),
        nullable=False, server_default=sa.true()))
    op.add_column("company_setting", sa.Column("email_to_unverified", sa.Boolean(),
        nullable=False, server_default=sa.true()))
def downgrade():
    op.drop_column("company_setting", "email_to_unverified")
    op.drop_column("company_setting", "circular_whatsapp_enabled")
    op.drop_column("company_setting", "circular_email_enabled")
