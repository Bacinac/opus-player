"""a profile's screensaver may show several people

Revision ID: 0023_screensaver_of_several
Revises: 0022_profile_screensaver
"""

import sqlalchemy as sa
from alembic import op


revision = "0023_screensaver_of_several"
down_revision = "0022_profile_screensaver"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "screensaver", type_=sa.String(160),
                    existing_type=sa.String(16), existing_nullable=False,
                    existing_server_default="")


def downgrade() -> None:
    op.execute("UPDATE users SET screensaver = split_part(screensaver, ',', 1)")
    op.alter_column("users", "screensaver", type_=sa.String(16),
                    existing_type=sa.String(160), existing_nullable=False,
                    existing_server_default="")
