"""every song heard is written down, so most-listened can be counted

Revision ID: 0018_music_plays
Revises: 0017_box_preferences
"""

import sqlalchemy as sa
from alembic import op


revision = "0018_music_plays"
down_revision = "0017_box_preferences"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_plays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("release_id", sa.Integer(), nullable=False),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("played_at", sa.DateTime(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_music_plays_user_played", "music_plays", ["user_id", "played_at"])


def downgrade() -> None:
    op.drop_index("ix_music_plays_user_played", table_name="music_plays")
    op.drop_table("music_plays")
