"""people in the house, and progress that belongs to one of them

Revision ID: 0002_users
Revises: 0001_initial
Create Date: 2026-08-16

"""
import sqlalchemy as sa
from alembic import op

revision = '0002_users'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('colour', sa.String(length=16), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    # what was recorded before anybody had a name cannot be attributed to one,
    # and a bookmark on the wrong person's shelf is worse than no bookmark
    op.execute('DELETE FROM progress')
    op.drop_constraint('progress_kind_item_id_key', 'progress', type_='unique')
    op.add_column('progress', sa.Column('user_id', sa.Integer(), nullable=False))
    op.create_foreign_key('progress_user_id_fkey', 'progress', 'users',
                          ['user_id'], ['id'], ondelete='CASCADE')
    op.create_index(op.f('ix_progress_user_id'), 'progress', ['user_id'], unique=False)
    op.create_unique_constraint('progress_user_kind_item_key', 'progress',
                                ['user_id', 'kind', 'item_id'])


def downgrade():
    op.drop_constraint('progress_user_kind_item_key', 'progress', type_='unique')
    op.drop_index(op.f('ix_progress_user_id'), table_name='progress')
    op.drop_constraint('progress_user_id_fkey', 'progress', type_='foreignkey')
    op.drop_column('progress', 'user_id')
    op.create_unique_constraint('progress_kind_item_id_key', 'progress',
                                ['kind', 'item_id'])
    op.drop_table('users')
