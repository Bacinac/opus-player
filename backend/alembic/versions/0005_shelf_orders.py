"""a shelf each, not one for all of them

Revision ID: 0005_shelf_orders
Revises: 0004_shelf_order
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_shelf_orders"
down_revision = "0004_shelf_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "shelf_order")
    op.add_column("users", sa.Column("shelf_orders", sa.String(200), nullable=False,
                                     server_default="{}"))


def downgrade() -> None:
    op.drop_column("users", "shelf_orders")
    op.add_column("users", sa.Column("shelf_order", sa.String(16), nullable=False,
                                     server_default="added"))
