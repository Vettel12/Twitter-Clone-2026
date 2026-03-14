import uuid
import aiofiles
from typing import List, Optional, cast
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, delete, select
from sqlalchemy.engine import CursorResult
from .models import Media, Tweet, Like


# Сохраняет файл на диск и создает запись в БД
async def save_media(db: AsyncSession, file: UploadFile) -> int:
    """
    Сохраняет файл на диск и создает запись в БД.
    
    SQL Equivalent:
    INSERT INTO media (file_path, tweet_id) VALUES (:file_path, NULL);
    """
    # 1. Создаем папку media, если нет
    media_dir = Path("media")
    media_dir.mkdir(exist_ok=True)

    # 2. Генерируем уникальное имя
    if file.filename:
        file_ext = Path(file.filename).suffix
    else:
        file_ext = "" 
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = media_dir / unique_filename

    # 3. Асинхронно читаем и записываем файл
    content = await file.read() 
    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(content)

    # 4. Сохраняем путь в БД
    db_media = Media(file_path=str(file_path))
    db.add(db_media)
    await db.commit()
    await db.refresh(db_media)

    return db_media.id


# Создание связи между твитом и медиа-файлом
async def create_tweet(
    db: AsyncSession, 
    author_id: int, 
    content: str, 
    media_ids: Optional[List[int]] = None
) -> int:
    """
    Создает твит и привязывает к нему медиа-файлы.
    
    SQL Equivalent:
    1. INSERT INTO tweets (content, author_id) VALUES (:content, :author_id) RETURNING id;
    2. UPDATE media SET tweet_id = :new_tweet_id WHERE id IN (:media_ids);
    """
    # 1. Создаем твит
    new_tweet = Tweet(
        content=content,
        author_id=author_id
    )
    db.add(new_tweet)
    await db.flush() # flush нужен, чтобы new_tweet получил ID из БД

    # 2. Если есть ID картинок, привязываем их к этому твиту
    if media_ids:
        stmt = (
            update(Media)
            .where(Media.id.in_(media_ids))
            .values(tweet_id=new_tweet.id)
        )
        await db.execute(stmt)

    await db.commit()
    await db.refresh(new_tweet)
    
    return new_tweet.id


async def add_like(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    """
    Ставит лайк. 
    Возвращает False, если твит не найден.
    
    SQL Equivalent:
    1. SELECT 1 FROM tweets WHERE id = :tweet_id;
    2. INSERT INTO likes (user_id, tweet_id) VALUES (:user_id, :tweet_id);
    """
    # Проверяем, существует ли твит
    tweet_res = await db.execute(select(Tweet).where(Tweet.id == tweet_id))
    if not tweet_res.scalar_one_or_none():
        return False
        
    # Создаем лайк
    like = Like(user_id=user_id, tweet_id=tweet_id)
    db.add(like)
    try:
        await db.commit()
        return True
    except Exception:
        # Если нарушена уникальность (уже лайкнул), откатываем
        await db.rollback()
        return False


async def remove_like(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    """
    Убирает лайк.
    
    SQL Equivalent:
    DELETE FROM likes WHERE user_id = :user_id AND tweet_id = :tweet_id;
    """
    stmt = delete(Like).where(
        Like.user_id == user_id, 
        Like.tweet_id == tweet_id
    )
    result = cast(CursorResult, await db.execute(stmt))
    await db.commit()
    return result.rowcount > 0


async def delete_tweet(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    """
    Удаляет твит, если пользователь — автор.
    
    SQL Equivalent:
    1. SELECT * FROM tweets WHERE id = :tweet_id;
    2. DELETE FROM tweets WHERE id = :tweet_id;
    """
    # Находим твит
    result = await db.execute(
        select(Tweet).where(Tweet.id == tweet_id)
    )
    tweet = result.scalar_one_or_none()
    
    if not tweet:
        return False
    
    # Проверка прав
    if tweet.author_id != user_id:
        raise PermissionError("Вы не можете удалить чужой твит")

    await db.delete(tweet)
    await db.commit()
    return True
