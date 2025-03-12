"""init migrate

Revision ID: 4be04886a604
Revises: 
Create Date: 2025-03-12 14:20:29.261015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4be04886a604'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('feeding_records', sa.Column('user_telegram_id', sa.Integer(), nullable=False))
    op.drop_constraint('feeding_records_user_id_fkey', 'feeding_records', type_='foreignkey')
    op.create_foreign_key(None, 'feeding_records', 'users', ['user_telegram_id'], ['telegram_id'])
    op.drop_column('feeding_records', 'user_id')
    op.add_column('sleep_records', sa.Column('user_telegram_id', sa.Integer(), nullable=False))
    op.create_foreign_key(None, 'sleep_records', 'users', ['user_telegram_id'], ['telegram_id'])
    op.drop_column('sleep_records', 'user_id')
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('sleep_records', sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'sleep_records', type_='foreignkey')
    op.drop_column('sleep_records', 'user_telegram_id')
    op.add_column('feeding_records', sa.Column('user_id', sa.INTEGER(), autoincrement=False, nullable=False))
    op.drop_constraint(None, 'feeding_records', type_='foreignkey')
    op.create_foreign_key('feeding_records_user_id_fkey', 'feeding_records', 'users', ['user_id'], ['id'])
    op.drop_column('feeding_records', 'user_telegram_id')
    # ### end Alembic commands ###
