"""the stereo output is the DAC on the player's own host, not the streamer it hung off

Revision ID: 0015_the_dac_is_the_players
Revises: 0014_no_place_in_a_station
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_the_dac_is_the_players"
down_revision = "0014_no_place_in_a_station"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "UPDATE settings SET value = 'dac' "
        "WHERE key = 'audio_output_stereo' AND value = 'volumio:ifi'"))


def downgrade() -> None:
    pass
