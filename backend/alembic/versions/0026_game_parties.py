"""the game played together

One screen asks, everybody answers on their own phone. The party holds the
questions and the clock; each player's answers stay a round of their own,
pointing back at it, so the house's standing counts a party like any round.
And a round writes down how hard its faces were asked for.

Revision ID: 0026_game_parties
Revises: 0025_box_wired_on_its_sink
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026_game_parties"
down_revision = "0025_box_wired_on_its_sink"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_parties",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), nullable=False),
        sa.Column("questions", postgresql.JSONB(), nullable=False),
        sa.Column("seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("hard", sa.Float(), nullable=True),
        sa.Column("asked_n", sa.Integer(), nullable=True),
        sa.Column("asked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revealed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_game_parties_host_id", "game_parties", ["host_id"])
    op.add_column("game_rounds", sa.Column("party_id", sa.Integer(), nullable=True))
    op.add_column("game_rounds", sa.Column("hard", sa.Float(), nullable=True))
    op.create_foreign_key("fk_game_rounds_party_id", "game_rounds", "game_parties",
                          ["party_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_game_rounds_party_id", "game_rounds", ["party_id"])


def downgrade() -> None:
    op.drop_index("ix_game_rounds_party_id", table_name="game_rounds")
    op.drop_constraint("fk_game_rounds_party_id", "game_rounds", type_="foreignkey")
    op.drop_column("game_rounds", "hard")
    op.drop_column("game_rounds", "party_id")
    op.drop_index("ix_game_parties_host_id", table_name="game_parties")
    op.drop_table("game_parties")
