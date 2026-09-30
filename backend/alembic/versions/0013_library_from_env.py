"""where Library answers and the token it is asked with come from the environment

Revision ID: 0013_library_from_env
Revises: 0012_cars_and_orphan_settings
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_library_from_env"
down_revision = "0012_cars_and_orphan_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM settings WHERE key IN ('library_url', 'library_token')"))


def downgrade() -> None:
    pass
