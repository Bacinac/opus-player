"""an episode watched is an episode of something

Revision ID: 0008_watched_parent
Revises: 0007_watched
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_watched_parent"
down_revision = "0007_watched"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("progress", sa.Column("parent_id", sa.Integer(), nullable=True))
    op.create_index("ix_progress_parent_id", "progress", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_progress_parent_id", table_name="progress")
    op.drop_column("progress", "parent_id")
