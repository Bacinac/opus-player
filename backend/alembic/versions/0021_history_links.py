"""a person's own ListenBrainz and Trakt, and what is on its way to them

Revision ID: 0021_history_links
Revises: 0020_first_shelf
"""

import sqlalchemy as sa
from alembic import op


revision = "0021_history_links"
down_revision = "0020_first_shelf"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "history_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service", sa.String(16), nullable=False),
        sa.Column("account", sa.String(128), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("refresh", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "service"),
    )
    op.create_table(
        "history_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tries", sa.Integer(), server_default="0", nullable=False),
        sa.Column("problem", sa.Text(), server_default="", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=True),
    )
    op.create_index("ix_history_outbox_due", "history_outbox", ["service", "due_at"])


def downgrade() -> None:
    op.drop_index("ix_history_outbox_due", table_name="history_outbox")
    op.drop_table("history_outbox")
    op.drop_table("history_links")
