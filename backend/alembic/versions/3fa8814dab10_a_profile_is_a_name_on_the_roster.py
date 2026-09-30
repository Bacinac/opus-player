"""a profile is a name on the roster

The profile table was a second list of who lives here, typed in again on every
surface and drifting from the first the day somebody was renamed. It becomes a
row that hangs off a name on the roster and holds only what the roster has no
opinion about — a colour, a language order, where somebody got to.

`is_admin` goes with it. Who may see the settings is one question and the roster
answers it now; two answers to it were exactly what the standing replaced.

What is deliberately NOT done here is matching the profiles already in this
table to names on the roster. That list lives in another module and is reached
over HTTP — a migration that needs the network is a migration that fails on the
one morning the other module is slow to come up. The matching happens the first
time somebody is picked instead, where the roster is being read anyway: a local
profile called "Filip" is adopted by the roster's `filip` rather than left beside
it, so nobody's half-finished films are stranded on the row they used to be.

Revision ID: 3fa8814dab10
Revises: 0009_radio
Create Date: 2026-08-29 05:26:28.035066

"""
from alembic import op
import sqlalchemy as sa


revision = '3fa8814dab10'
down_revision = '0009_radio'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('person', sa.String(length=64), nullable=True))
    op.drop_constraint(op.f('users_name_key'), 'users', type_='unique')
    op.create_unique_constraint('users_person_key', 'users', ['person'])
    # a name still has to be one person's, but only among those who are nobody
    # on the roster: everybody else is told apart by the name over there, and
    # two rows sharing a name here would have one of them silently disappear
    # from a list that is keyed by it
    op.create_index('ix_users_local_name', 'users', ['name'], unique=True,
                    postgresql_where=sa.text("person IS NULL AND name <> ''"))
    op.drop_column('users', 'is_admin')


def downgrade():
    op.add_column('users', sa.Column('is_admin', sa.BOOLEAN(),
                                     server_default=sa.text('false'),
                                     autoincrement=False, nullable=False))
    op.drop_index('ix_users_local_name', table_name='users')
    # somebody who was only ever a name on the roster has no name of their own
    # to go back to, so they take it now or they collide
    op.execute("UPDATE users SET name = person WHERE person IS NOT NULL AND name = ''")
    op.drop_constraint('users_person_key', 'users', type_='unique')
    op.create_unique_constraint(op.f('users_name_key'), 'users', ['name'])
    op.drop_column('users', 'person')
