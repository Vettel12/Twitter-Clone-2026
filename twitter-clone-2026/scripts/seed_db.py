# scripts/seed_db.py
import asyncio
import sys
import os

# Добавляем корень проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from libs.database import AsyncSessionLocal
from services.users.app.models import User
# !!! ВАЖНЫЙ ИМПОРТ: Загружаем модели, с которыми связан User, чтобы SQLAlchemy их увидел !!!
from services.tweets.app.models import Tweet, Like 

async def create_test_user():
    async with AsyncSessionLocal() as db:
        # Проверяем, есть ли уже юзер
        result = await db.execute(select(User).where(User.api_key == "test"))
        if result.scalar_one_or_none():
            print("User 'test' already exists.")
            return

        # Создаем тестового юзера
        new_user = User(name="Valera", api_key="test")
        db.add(new_user)
        await db.commit()
        print("User created! Name: Valera, API-Key: test")

if __name__ == "__main__":
    asyncio.run(create_test_user())
