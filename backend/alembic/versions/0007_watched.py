"""a profile remembers what it finished, not only where it stopped

Revision ID: 0007_watched
Revises: 0006_language_order
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_watched"
down_revision = "0006_language_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("progress",
                  sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("progress", "finished_at")
