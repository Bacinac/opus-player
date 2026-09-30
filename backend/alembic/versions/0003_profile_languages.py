"""a profile watches in its own language

Revision ID: 0003_profile_languages
Revises: 0002_users
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_profile_languages"
down_revision = "0002_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("audio_language", sa.String(8), nullable=False,
                                     server_default=""))
    op.add_column("users", sa.Column("subtitle_language", sa.String(8), nullable=False,
                                     server_default=""))


def downgrade() -> None:
    op.drop_column("users", "subtitle_language")
    op.drop_column("users", "audio_language")
