"""progress: the unique key already leads with user_id

Revision ID: 0011_progress_user_index
Revises: 0010_game_rounds
"""

from alembic import op

revision = "0011_progress_user_index"
down_revision = "0010_game_rounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_progress_user_id", table_name="progress")


def downgrade() -> None:
    op.create_index("ix_progress_user_id", "progress", ["user_id"])
