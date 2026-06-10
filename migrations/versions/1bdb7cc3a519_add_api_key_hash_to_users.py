"""add_api_key_hash_to_users

Revision ID: 1bdb7cc3a519
Revises: 68cf89fc1c2c
Create Date: 2026-04-11 09:04:42.173978

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1bdb7cc3a519'
down_revision: Union[str, Sequence[str], None] = '68cf89fc1c2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add api_key_hash column."""
    # 1. Добавляем новый столбец с дефолтным значением (временно)
    op.add_column('users', sa.Column('api_key_hash', sa.String(length=64), nullable=True))
    
    # 2. Копируем данные из api_key в api_key_hash (они уже являются хешами)
    op.execute("""
        UPDATE users 
        SET api_key_hash = SUBSTRING(api_key, 1, 64)
        WHERE api_key IS NOT NULL
    """)
    
    # 3. Делаем столбец NOT NULL
    op.alter_column('users', 'api_key_hash', nullable=False)
    
    # 4. Удаляем старый столбец api_key
    op.drop_constraint('users_api_key_key', 'users', type_='unique')
    op.drop_column('users', 'api_key')
    
    # 5. Добавляем unique constraint на api_key_hash
    op.create_unique_constraint('users_api_key_hash_key', 'users', ['api_key_hash'])


def downgrade() -> None:
    """Downgrade schema - revert to api_key column."""
    # 1. Удаляем unique constraint
    op.drop_constraint('users_api_key_hash_key', 'users', type_='unique')
    
    # 2. Добавляем обратно api_key столбец
    op.add_column('users', sa.Column('api_key', sa.String(length=255), nullable=True))
    
    # 3. Копируем данные из api_key_hash обратно
    op.execute("""
        UPDATE users 
        SET api_key = api_key_hash
        WHERE api_key_hash IS NOT NULL
    """)
    
    # 4. Делаем NOT NULL
    op.alter_column('users', 'api_key', nullable=False)
    
    # 5. Добавляем unique constraint
    op.create_unique_constraint('users_api_key_key', 'users', ['api_key'])
    
    # 6. Удаляем api_key_hash
    op.drop_column('users', 'api_key_hash')
