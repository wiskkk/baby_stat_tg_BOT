"""Add chat_id to feeding_records

Revision ID: 9e0100b68a2b
Revises: 3f2645a552b6
Create Date: 2025-03-31 12:10:23.797959

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9e0100b68a2b'
down_revision: Union[str, None] = '3f2645a552b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    # Добавляем столбец без NOT NULL
    op.add_column('feeding_records', sa.Column('chat_id', sa.BigInteger(), nullable=True))

    # Заполняем значения в новом столбце
    op.execute("UPDATE feeding_records SET chat_id = user_telegram_id")

    # Добавляем ограничение NOT NULL
    op.alter_column('feeding_records', 'chat_id', nullable=False)

    # Добавляем внешний ключ
    op.create_foreign_key(
        'feeding_records_chat_id_fkey',
        'feeding_records',
        'users',
        ['chat_id'],
        ['chat_id']
    )

    # Удаляем старый столбец
    op.drop_column('feeding_records', 'user_telegram_id')

def downgrade():
    # Возвращаем старый столбец
    op.add_column('feeding_records', sa.Column('user_telegram_id', sa.BigInteger(), nullable=False))

    # Заполняем значения в старом столбце
    op.execute("UPDATE feeding_records SET user_telegram_id = chat_id")

    # Удаляем новый столбец
    op.drop_constraint('feeding_records_chat_id_fkey', 'feeding_records', type_='foreignkey')
    op.drop_column('feeding_records', 'chat_id')