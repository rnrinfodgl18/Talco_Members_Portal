"""Company, SMTP, logo, and user profile settings."""
from alembic import op
import sqlalchemy as sa

revision = "0010_application_settings"
down_revision = "0009_complete_tally_import"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("app_user", sa.Column("display_name", sa.String(120)))
    op.add_column("app_user", sa.Column("phone", sa.String(30)))
    op.create_table("company_setting",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(100), nullable=False),
        sa.Column("address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("state", sa.String(100)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("gstin", sa.String(20)),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(255)),
        sa.Column("website", sa.String(255)),
        sa.Column("logo_data", sa.LargeBinary()),
        sa.Column("logo_mime", sa.String(50)),
        sa.Column("smtp_host", sa.String(255)),
        sa.Column("smtp_port", sa.Integer()),
        sa.Column("smtp_username", sa.String(255)),
        sa.Column("smtp_password", sa.Text()),
        sa.Column("smtp_from_email", sa.String(255)),
        sa.Column("smtp_from_name", sa.String(255)),
        sa.Column("smtp_security", sa.String(20), server_default="starttls", nullable=False),
        sa.Column("smtp_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.execute("""INSERT INTO company_setting
        (id, company_name, short_name, address, city, state, postal_code, gstin)
        VALUES (1, 'Talco-Dindigul Tanners Enviro Control Systems P Ltd', 'TALCO-DINTEC',
        'Batlagundu Road, Begampur Post', 'Dindigul', 'Tamil Nadu', '624002', '33AAACT2664C1ZS')""")

def downgrade():
    op.drop_table("company_setting")
    op.drop_column("app_user", "phone")
    op.drop_column("app_user", "display_name")
