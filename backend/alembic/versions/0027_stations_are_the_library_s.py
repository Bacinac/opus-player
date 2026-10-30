"""stations are the library's

The list of stations moved to the Library, which keeps everything that exists
to be listened to and the logos with it. The player asks for it; the relay of a
live stream is all that stays here.

Revision ID: 0027_stations_are_the_library_s
Revises: 0026_game_parties
"""

import sqlalchemy as sa
from alembic import op

revision = "0027_stations_are_the_library_s"
down_revision = "0026_game_parties"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("radio_stations")


def downgrade() -> None:
    op.create_table(
        "radio_stations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("genre", sa.String(200), nullable=False, server_default=""),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("logo", sa.Text()),
        sa.Column("country", sa.String(8), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
