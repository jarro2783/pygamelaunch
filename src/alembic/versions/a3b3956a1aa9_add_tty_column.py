"""Add tty column

Revision ID: a3b3956a1aa9
Revises: 6cb6373ad91b
Create Date: 2016-07-05 19:06:13.903122

"""

# revision identifiers, used by Alembic.
revision = 'a3b3956a1aa9'
down_revision = '6cb6373ad91b'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('playing', sa.Column('record', sa.String(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('playing', 'record')
    ### end Alembic commands ###