"""Phase 5 authentication and RBAC."""

from alembic import op
import sqlalchemy as sa

revision = "0004_phase5_auth"
down_revision = "0003_normalized_gstin_width"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("app_user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255)),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("tannery_id", sa.Integer(), sa.ForeignKey("tannery.id")),
        sa.Column("party_id", sa.Integer(), sa.ForeignKey("party.id")),
        sa.Column("must_set_password", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_check_constraint("ck_app_user_role", "app_user",
        "role IN ('talco_admin','talco_staff','member','member_staff','lessee')")
    op.create_table("auth_token",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.create_index("ix_auth_token_user_purpose", "auth_token", ["user_id", "purpose"])


def downgrade() -> None:
    op.drop_table("auth_token")
    op.drop_table("app_user")
