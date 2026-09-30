"""a station has no place to come back to

Revision ID: 0014_no_place_in_a_station
Revises: 0013_library_from_env
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_no_place_in_a_station"
down_revision = "0013_library_from_env"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM progress WHERE item_id < 1"))


def downgrade() -> None:
    pass
