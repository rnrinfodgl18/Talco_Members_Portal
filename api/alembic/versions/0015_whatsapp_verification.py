"""Add WhatsApp configuration and phone verification."""
from alembic import op
import sqlalchemy as sa

revision = "0015_whatsapp_verification"
down_revision = "0014_custom_theme"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("company_setting", sa.Column("whatsapp_base_url", sa.String(500), nullable=True))
    op.add_column("company_setting", sa.Column("whatsapp_api_key", sa.Text(), nullable=True))
    op.add_column("company_setting", sa.Column("whatsapp_device_id", sa.Integer(), nullable=True))
    op.add_column("company_setting", sa.Column("whatsapp_enabled", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("app_user", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("app_user", "phone_verified_at")
    op.drop_column("company_setting", "whatsapp_enabled")
    op.drop_column("company_setting", "whatsapp_device_id")
    op.drop_column("company_setting", "whatsapp_api_key")
    op.drop_column("company_setting", "whatsapp_base_url")

