"""a profile answers with an order of languages, not one

Revision ID: 0006_language_order
Revises: 0005_shelf_orders
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_language_order"
down_revision = "0005_shelf_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for old, new in (("audio_language", "audio_languages"),
                     ("subtitle_language", "subtitle_languages")):
        op.alter_column("users", old, new_column_name=new,
                        type_=sa.String(32), existing_type=sa.String(8))


def downgrade() -> None:
    for new, old in (("audio_languages", "audio_language"),
                     ("subtitle_languages", "subtitle_language")):
        op.alter_column("users", new, new_column_name=old,
                        type_=sa.String(8), existing_type=sa.String(32))
