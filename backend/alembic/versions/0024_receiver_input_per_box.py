"""the receiver's input belongs to each box, not to the install

Revision ID: 0024_receiver_input_per_box
Revises: 0023_screensaver_of_several
"""

import sqlalchemy as sa
from alembic import op


revision = "0024_receiver_input_per_box"
down_revision = "0023_screensaver_of_several"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("box_preferences", sa.Column("amp_source", sa.String(32),
                                               server_default="", nullable=False))
    # the one input the install had was the house's television's, and "SHIELD"
    # was what it said while nobody had changed it
    op.execute("""
        INSERT INTO box_preferences (box_id, shelf_orders, amp_source)
        SELECT tv.value::int, '{}',
               coalesce((SELECT value FROM settings WHERE key = 'audio_amp_source_multi'), 'SHIELD')
        FROM settings tv WHERE tv.key = 'tv_box' AND tv.value ~ '^[0-9]+$'
        ON CONFLICT (box_id) DO UPDATE SET amp_source = excluded.amp_source
    """)
    op.execute("DELETE FROM settings WHERE key = 'audio_amp_source_multi'")


def downgrade() -> None:
    op.execute("""
        INSERT INTO settings (key, value)
        SELECT 'audio_amp_source_multi', b.amp_source
        FROM box_preferences b JOIN settings tv ON tv.key = 'tv_box' AND tv.value = b.box_id::text
        WHERE b.amp_source <> ''
    """)
    op.drop_column("box_preferences", "amp_source")
