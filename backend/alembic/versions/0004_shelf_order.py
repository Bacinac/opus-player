"""a viewer arranges their own shelves

Revision ID: 0004_shelf_order
Revises: 0003_profile_languages
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_shelf_order"
down_revision = "0003_profile_languages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("shelf_order", sa.String(16), nullable=False,
                                     server_default="added"))


def downgrade() -> None:
    op.drop_column("users", "shelf_order")
