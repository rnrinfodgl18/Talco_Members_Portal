"""Dashboards, PWA notifications, push subscriptions and email verification."""
from alembic import op
import sqlalchemy as sa

revision = "0012_dashboard_pwa_notifications"
down_revision = "0011_circulars_notice_board"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("app_user", sa.Column("email_verified_at", sa.DateTime(timezone=True)))
    op.create_table("notification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False), sa.Column("link", sa.String(500)),
        sa.Column("entity_type", sa.String(50)), sa.Column("entity_id", sa.Integer()),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_notification_user_id", "notification", ["user_id"])
    op.create_table("push_subscription",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("endpoint", sa.Text(), unique=True, nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False), sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_push_subscription_user_id", "push_subscription", ["user_id"])
    op.create_table("delivery_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="SET NULL")),
        sa.Column("notification_id", sa.Integer(), sa.ForeignKey("notification.id", ondelete="SET NULL")),
        sa.Column("channel", sa.String(20), nullable=False), sa.Column("destination", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("detail", sa.Text()),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now()))

def downgrade():
    op.drop_table("delivery_log")
    op.drop_index("ix_push_subscription_user_id", table_name="push_subscription")
    op.drop_table("push_subscription")
    op.drop_index("ix_notification_user_id", table_name="notification")
    op.drop_table("notification")
    op.drop_column("app_user", "email_verified_at")
