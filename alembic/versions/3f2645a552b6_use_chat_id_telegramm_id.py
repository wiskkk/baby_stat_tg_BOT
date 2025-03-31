"""use chat_id -> telegramm_id

Revision ID: 3f2645a552b6
Revises: 72b1332a40a7
Create Date: 2025-03-31 08:35:59.168430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f2645a552b6'
down_revision: Union[str, None] = '72b1332a40a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Переименовываем колонку telegram_id в chat_id
    op.execute('ALTER TABLE users RENAME COLUMN telegram_id TO chat_id')

def downgrade():
    # Откат изменений
    op.execute('ALTER TABLE users RENAME COLUMN chat_id TO telegram_id')