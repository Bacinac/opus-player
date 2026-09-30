"""the guessing game

Ten photographs and what somebody answered about them. One row per round: the
questions were built from the library together and only mean anything together,
and the round's total is read from the answers rather than kept beside them.

Revision ID: 0010_game_rounds
Revises: 3fa8814dab10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_game_rounds"
down_revision = "3fa8814dab10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_rounds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("answers", postgresql.JSONB(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("asked_n", sa.Integer(), nullable=True),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_game_rounds_user_id", "game_rounds", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_game_rounds_user_id", table_name="game_rounds")
    op.drop_table("game_rounds")
