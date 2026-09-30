"""a car is a row of its own, and settings are only what the spec names

A car's bearer now carries the id of a row here, so one lost phone is taken back
without its owner signing out of everything else. Bearers minted before this
carry no id and are refused: each car pairs once more.

Settings nothing reads any more are dropped — the old household door left its
username and password behind in the clear. And the three addresses that were
written into the code as defaults were this household's machines: an install
that has been running keeps exactly the address it was reading, a fresh one
starts with none.

Revision ID: 0012_cars_and_orphan_settings
Revises: 0011_progress_user_index
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_cars_and_orphan_settings"
down_revision = "0011_progress_user_index"
branch_labels = None
depends_on = None

SPEC_KEYS = (
    "library_url", "library_token",
    "dida_url", "dida_username", "dida_password", "dida_panel_key",
    "audio_output_stereo", "audio_output_multi", "audio_volume_entity",
    "audio_amp_entity", "audio_amp_source", "audio_amp_source_multi",
    "stream_base",
)

FORMER_DEFAULTS = {
    "library_url": "http://192.168.1.103:8095",
    "dida_url": "http://192.168.1.100:5273",
    "stream_base": "http://192.168.1.102:8098",
}


def upgrade() -> None:
    op.create_table(
        "car_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("person", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_car_tokens_person", "car_tokens", ["person"])

    settled = op.get_bind().scalar(sa.text("SELECT count(*) FROM settings"))
    op.execute(sa.text("DELETE FROM settings WHERE key NOT IN :keys")
               .bindparams(sa.bindparam("keys", SPEC_KEYS, expanding=True)))
    if settled:
        for key, value in FORMER_DEFAULTS.items():
            op.execute(sa.text(
                "INSERT INTO settings (key, value) VALUES (:key, :value) "
                "ON CONFLICT (key) DO NOTHING").bindparams(key=key, value=value))


def downgrade() -> None:
    op.drop_index("ix_car_tokens_person", table_name="car_tokens")
    op.drop_table("car_tokens")
