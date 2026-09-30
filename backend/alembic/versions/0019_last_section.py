"""a television opens where it was left

Revision ID: 0019_last_section
Revises: 0018_music_plays
"""

import sqlalchemy as sa
from alembic import op


revision = "0019_last_section"
down_revision = "0018_music_plays"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("users", "box_preferences"):
        op.add_column(table, sa.Column("last_section", sa.String(length=16),
                                       nullable=False, server_default=""))


def downgrade() -> None:
    for table in ("users", "box_preferences"):
        op.drop_column(table, "last_section")
