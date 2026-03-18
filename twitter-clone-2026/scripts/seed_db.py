# scripts/seed_db.py
import asyncio
import os
import sys

# Добавляем корень проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

# !!! ВАЖНЫЙ ИМПОРТ: Загружаем модели, с которыми связан User, чтобы SQLAlchemy их увидел !!!
from libs.database import AsyncSessionLocal
from services.users.app.models import User


async def create_test_user() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.api_key == "test"))
        if result.scalar_one_or_none():
            print("User 'test' already exists.")
            return

        new_user = User(name="Valera", api_key="test")
        db.add(new_user)
        await db.commit()
        print("User created! Name: Valera, API-Key: test")


if __name__ == "__main__":
    asyncio.run(create_test_user())
