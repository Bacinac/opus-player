"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-15

"""
import sqlalchemy as sa
from alembic import op

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'settings',
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )
    op.create_table(
        'progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('position_s', sa.Float(), nullable=False),
        sa.Column('duration_s', sa.Float(), nullable=True),
        sa.Column('surface', sa.String(length=16), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('kind', 'item_id'),
    )
    op.create_index(op.f('ix_progress_item_id'), 'progress', ['item_id'], unique=False)


def downgrade():
    op.drop_table('progress')
    op.drop_table('settings')
