from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from .models import User, Follower


# 1. Получение информации о свем профиле
async def get_user_by_api_key(db: AsyncSession, api_key: str) -> User | None:
    """
    Получает пользователя по API-ключу.
    Используется для аутентификации.
    SELECT * FROM users WHERE api_key = :api_key
    """
    query = select(User).where(User.api_key == api_key)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# 2. Получение информации о о пользователе по id
async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """
    Получает профиль пользователя по ID с загрузкой подписчиков.
    selectinload нужен, чтобы сразу вытащить related objects (followers/following)
    и не спамить базу лишними запросами при сериализации.
    SELECT * FROM users WHERE id = :user_id
    """
    query = (
        select(User)
        .options(
            selectinload(User.followers),
            selectinload(User.following)
        )
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


# 3. Подписка на другого пользователя по id
async def follow_user(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    """
    Подписка на пользователя.
    SELECT * FROM followers WHERE follower_id = :follower_id AND followed_id = :followed_id
    """
    # Проверка: пытается ли пользователь подписаться на самого себя
    if follower_id == followed_id:
        return False
    
    # Проверяем, нет ли уже подписки
    existing = await db.execute(
        select(Follower).where(
            Follower.follower_id == follower_id,
            Follower.followed_id == followed_id
        )
    )

    if existing.scalar_one_or_none():
        return False  # Уже подписан
    

    # Создаем связь
    new_follow = Follower(follower_id=follower_id, followed_id=followed_id)
    db.add(new_follow)
    await db.commit()
    return True


# 4. Отписка от другого пользователя по id
async def unfollow_user(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    """
    Отписка от пользователя.
    DELETE FROM followers WHERE follower_id = :follower_id AND followed_id = :followed_id
    """
    stmt = delete(Follower).where(
        Follower.follower_id == follower_id,
        Follower.followed_id == followed_id
    )

    result = await db.execute(stmt)
    await db.commit()
    # result.rowcount показывает, сколько строк было удалено
    return result.rowcount > 0
