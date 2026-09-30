"""a television without a profile keeps its shelf orders

Revision ID: 0017_box_preferences
Revises: 0016_music_favorites
"""

import sqlalchemy as sa
from alembic import op


revision = "0017_box_preferences"
down_revision = "0016_music_favorites"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "box_preferences",
        sa.Column("box_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("shelf_orders", sa.String(length=200), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_table("box_preferences")
