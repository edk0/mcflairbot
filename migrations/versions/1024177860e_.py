"""empty message

Revision ID: 1024177860e
Revises: 1c1100da6c4
Create Date: 2014-12-24 23:13:56.979548

"""

# revision identifiers, used by Alembic.
revision = '1024177860e'
down_revision = '1c1100da6c4'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('giveaway_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('trade_id', sa.String(length=32), nullable=True),
    sa.Column('target', sa.String(length=32), nullable=True),
    sa.Column('target_flair', sa.String(length=256), nullable=True),
    sa.Column('target_flair_css', sa.String(length=64), nullable=True),
    sa.Column('target_ip', sa.String(length=64), nullable=True),
    sa.Column('time', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['trade_id'], ['trade.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('giveaway_log')
    ### end Alembic commands ###
