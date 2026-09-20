"""Allow accounts with no email: many tannery owners have no reliable address."""
from alembic import op
import sqlalchemy as sa
revision = "0018_optional_user_email"
down_revision = "0017_company_bank_details"
branch_labels = None
depends_on = None
def upgrade():
    op.alter_column("app_user", "email", existing_type=sa.String(255), nullable=True)
def downgrade():
    op.execute("UPDATE app_user SET email = 'user-' || id || '@placeholder.invalid' WHERE email IS NULL")
    op.alter_column("app_user", "email", existing_type=sa.String(255), nullable=False)
