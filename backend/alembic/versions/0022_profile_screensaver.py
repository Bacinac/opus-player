"""whose photographs a profile's screensaver shows

Revision ID: 0022_profile_screensaver
Revises: 0021_history_links
"""

import sqlalchemy as sa
from alembic import op


revision = "0022_profile_screensaver"
down_revision = "0021_history_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("screensaver", sa.String(16),
                                     server_default="", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "screensaver")
