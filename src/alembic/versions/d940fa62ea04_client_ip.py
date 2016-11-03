"""client_ip

Revision ID: d940fa62ea04
Revises: f04c63b52c8e
Create Date: 2016-11-03 18:38:05.908844

"""

# revision identifiers, used by Alembic.
revision = 'd940fa62ea04'
down_revision = 'f04c63b52c8e'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('logins', sa.Column('client', sa.String(), nullable=True))
    op.create_index(op.f('ix_logins_success'), 'logins', ['success'], unique=False)
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_logins_success'), table_name='logins')
    op.drop_column('logins', 'client')
    ### end Alembic commands ###
