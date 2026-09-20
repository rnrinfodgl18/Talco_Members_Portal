"""Record which roles a role-wise circular targeted."""
from alembic import op
import sqlalchemy as sa
revision = "0020_circular_audience_roles"
down_revision = "0019_notification_channels"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("circular", sa.Column("audience_roles", sa.String(120), nullable=True))
def downgrade():
    op.drop_column("circular", "audience_roles")
