"""a record somebody wants to find again

Revision ID: 0016_music_favorites
Revises: 0015_the_dac_is_the_players
"""

import sqlalchemy as sa
from alembic import op


revision = "0016_music_favorites"
down_revision = "0015_the_dac_is_the_players"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "music_favorites",
        sa.Column("id", sa.Integer(), primary_key=True),
        # This is a roster key, deliberately not a foreign key to ``users``:
        # paired cars prove a person but do not choose a television profile.
        sa.Column("person", sa.String(length=64), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("person", "track_id"),
    )
    op.create_index("ix_music_favorites_person", "music_favorites", ["person"])
    op.create_index("ix_music_favorites_person_created", "music_favorites",
                    ["person", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_music_favorites_person_created", table_name="music_favorites")
    op.drop_index("ix_music_favorites_person", table_name="music_favorites")
    op.drop_table("music_favorites")
