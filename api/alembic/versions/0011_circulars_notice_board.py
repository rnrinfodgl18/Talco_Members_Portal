"""Circular publishing, targeted delivery, attachments and read receipts."""
from alembic import op
import sqlalchemy as sa

revision = "0011_circulars_notice_board"
down_revision = "0010_application_settings"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("circular",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("category", sa.String(40), server_default="general", nullable=False),
        sa.Column("priority", sa.String(20), server_default="normal", nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="published", nullable=False),
        sa.Column("expires_on", sa.Date()),
        sa.Column("attachment_name", sa.String(255)),
        sa.Column("attachment_mime", sa.String(100)),
        sa.Column("attachment_data", sa.LargeBinary()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_table("circular_recipient",
        sa.Column("circular_id", sa.Integer(), sa.ForeignKey("circular.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("circular_read",
        sa.Column("circular_id", sa.Integer(), sa.ForeignKey("circular.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_circular_status_published", "circular", ["status", "published_at"])

def downgrade():
    op.drop_index("ix_circular_status_published", table_name="circular")
    op.drop_table("circular_read")
    op.drop_table("circular_recipient")
    op.drop_table("circular")
