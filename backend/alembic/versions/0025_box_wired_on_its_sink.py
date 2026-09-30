"""a box's receiver input holds while it is plugged into what it was wired on

Revision ID: 0025_box_wired_on_its_sink
Revises: 0024_receiver_input_per_box
"""

import sqlalchemy as sa
from alembic import op


revision = "0025_box_wired_on_its_sink"
down_revision = "0024_receiver_input_per_box"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("box_preferences", sa.Column("amp_sink", sa.String(160),
                                               server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("box_preferences", "amp_sink")
