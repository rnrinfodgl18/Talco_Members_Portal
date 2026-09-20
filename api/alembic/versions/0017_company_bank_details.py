"""Add company bank details for the invoice bank block."""
from alembic import op
import sqlalchemy as sa
revision = "0017_company_bank_details"
down_revision = "0016_user_username"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("company_setting", sa.Column("bank_name", sa.String(255), nullable=True))
    op.add_column("company_setting", sa.Column("bank_account_number", sa.String(50), nullable=True))
    op.add_column("company_setting", sa.Column("bank_branch", sa.String(255), nullable=True))
    op.add_column("company_setting", sa.Column("bank_ifsc", sa.String(20), nullable=True))
def downgrade():
    op.drop_column("company_setting", "bank_ifsc")
    op.drop_column("company_setting", "bank_branch")
    op.drop_column("company_setting", "bank_account_number")
    op.drop_column("company_setting", "bank_name")
