"""move deleted state to its own column

Revision ID: 9a3542295c
Revises: 4169d11408
Create Date: 2014-08-01 19:09:47.147388

"""

# revision identifiers, used by Alembic.
revision = '9a3542295c'
down_revision = '4169d11408'

from alembic import op
import sqlalchemy as sa
import sqlalchemy.sql as sql


trade = sql.table('trade',
    sql.column('status', sa.Enum('valid', 'invalid', 'finished', 'deleted')),
    sql.column('deleted', sa.Boolean())
)


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('trade', sa.Column('deleted', sa.Boolean(), nullable=True))
    ### end Alembic commands ###
    op.execute(trade.update().\
        where(trade.c.status == 'deleted').\
        values({'status': 'finished', 'deleted': True})
        )


def downgrade():
    op.execute(trade.update().\
        where(trade.c.deleted == True).\
        values({'status': 'deleted'})
        )
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('trade', 'deleted')
    ### end Alembic commands ###