"""a television opens on the first shelf there is anything on

Revision ID: 0020_first_shelf
Revises: 0019_last_section
"""

import sqlalchemy as sa
from alembic import op


revision = "0020_first_shelf"
down_revision = "0019_last_section"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("users", "box_preferences"):
        op.drop_column(table, "last_section")


def downgrade() -> None:
    for table in ("users", "box_preferences"):
        op.add_column(table, sa.Column("last_section", sa.String(length=16),
                                       nullable=False, server_default=""))
