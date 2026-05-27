from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from libs.config import settings

# 1. Создаем асинхронный движок
# ✅ FIXED: echo берется из конфига (НИКОГДА True в production!)
engine = create_async_engine(
    settings.sqlalchemy_database_url,
    echo=settings.sqlalchemy_echo,
)

# 2. Создаем фабрику сессий
# expire_on_commit=False позволяет читать данные объекта после коммита (удобно)
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


# 3. Базовый класс для моделей
class Base(DeclarativeBase):
    pass


# 4. Зависимость (Dependency) для FastAPI
# Она будет внедряться в эндпоинты через Depends(get_db)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
