import logging
from pathlib import Path
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database import get_db
from libs.redis_client import get_redis
from services.tweets.app import crud, schemas
from services.users.app.crud import get_user_by_api_key
from services.users.app.models import User

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Зависимость для авторизации ---
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Header(alias="api-key")] = None,
) -> User:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")

    user = await get_user_by_api_key(db, api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user


# --- Эндпоинты ---


@router.post("/api/medias", response_model=schemas.MediaUploadResponse)
async def upload_media(
    file: Annotated[UploadFile, File(...)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    logger.info(f"User {user.id} uploading media: {file.filename}")
    media_id = await crud.save_media(db, file)
    logger.info(f"Media saved with ID: {media_id}")
    return schemas.MediaUploadResponse(media_id=media_id)


@router.post("/api/tweets", response_model=schemas.TweetCreateResponse)
async def create_tweet(
    tweet_data: schemas.TweetCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    logger.info(
        f"User {user.id} creating tweet with content: '{tweet_data.tweet_data[:20]}...'"
    )
    tweet_id = await crud.create_tweet(
        db,
        author_id=user.id,
        content=tweet_data.tweet_data,
        media_ids=tweet_data.tweet_media_ids,
    )
    logger.info(f"Tweet {tweet_id} created successfully by user {user.id}")
    return schemas.TweetCreateResponse(tweet_id=tweet_id)


@router.delete("/api/tweets/{tweet_id}")
async def delete_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    logger.info(f"User {user.id} attempting to delete tweet {tweet_id}")
    try:
        success = await crud.delete_tweet(db, user.id, tweet_id)
        if not success:
            logger.warning(f"Tweet {tweet_id} not found for deletion")
            return {
                "result": False,
                "error_type": "NotFoundError",
                "error_message": "Tweet not found",
            }
        r = await get_redis()
        # Удаляем кэш ленты текущего пользователя, чтобы он сразу увидел изменение
        await r.delete(f"feed:{user.id}")
        logger.info(f"Tweet {tweet_id} deleted by user {user.id}")
        return {"result": True}
    except PermissionError as e:
        logger.warning(f"Permission denied for user {user.id} on tweet {tweet_id}: {e}")
        return {
            "result": False,
            "error_type": "PermissionError",
            "error_message": str(e),
        }


@router.post("/api/tweets/{tweet_id}/likes")
async def like_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    user_id = user.id
    logger.info(f"[LIKE] START: User {user_id} liking tweet {tweet_id}")

    # 1. Добавляем лайк в БД
    success = await crud.add_like(db, user_id, tweet_id)
    if not success:
        logger.warning(
            f"[LIKE] FAILED: User {user_id} tweet {tweet_id} (already liked or not found)"
        )
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Cannot like tweet (already liked or not found)",
        }

    logger.info("[LIKE] DB_UPDATE: Like added to DB")

    # 2. Получаем пост, чтобы узнать автора
    updated_tweet = await crud.get_tweet_by_id(db, tweet_id)

    # 3. Инвалидируем кэш ленты текущего пользователя И автора поста
    r = await get_redis()
    await r.delete(f"feed:{user_id}")
    if updated_tweet:
        await r.delete(f"feed:{updated_tweet.author_id}")
        logger.info(
            f"[LIKE] CACHE_INVALIDATED: feed:{user_id} and feed:{updated_tweet.author_id}"
        )
    else:
        logger.info(f"[LIKE] CACHE_INVALIDATED: feed:{user_id}")
    logger.info(
        f"[LIKE] TWEET_FETCHED: {tweet_id} with {len(updated_tweet.likes) if updated_tweet else 0} likes"
    )

    if updated_tweet and updated_tweet.likes:
        likes_list = [
            schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
            for like in updated_tweet.likes
        ]
        attachments_list = [f"/media/{Path(media.file_path).name}" for media in updated_tweet.media]
        tweet_out = schemas.TweetOut(
            id=updated_tweet.id,
            content=updated_tweet.content,
            created_at=updated_tweet.created_at,
            author=schemas.UserInTweet.model_validate(updated_tweet.author),
            attachments=attachments_list,
            likes=likes_list,
        )
        logger.info(
            f"[LIKE] SUCCESS: Returning updated tweet with {len(likes_list)} likes"
        )
        return {"result": True, "tweet": tweet_out}

    logger.warning("[LIKE] WARNING: Tweet not found after like")
    return {"result": True}


@router.delete("/api/tweets/{tweet_id}/likes")
async def unlike_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    user_id = user.id
    logger.info(f"[UNLIKE] START: User {user_id} unliking tweet {tweet_id}")

    # 1. Удаляем лайк из БД
    success = await crud.remove_like(db, user_id, tweet_id)
    if not success:
        logger.warning(f"[UNLIKE] FAILED: User {user_id} tweet {tweet_id} (not found)")
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Like not found",
        }

    logger.info("[UNLIKE] DB_UPDATE: Like removed from DB")

    # 2. Получаем пост, чтобы узнать автора
    updated_tweet = await crud.get_tweet_by_id(db, tweet_id)

    # 3. Инвалидируем кэш ленты текущего пользователя И автора поста
    r = await get_redis()
    await r.delete(f"feed:{user_id}")
    if updated_tweet:
        await r.delete(f"feed:{updated_tweet.author_id}")
        logger.info(
            f"[UNLIKE] CACHE_INVALIDATED: feed:{user_id} and feed:{updated_tweet.author_id}"
        )
    else:
        logger.info(f"[UNLIKE] CACHE_INVALIDATED: feed:{user_id}")
    logger.info(
        f"[UNLIKE] TWEET_FETCHED: {tweet_id} with {len(updated_tweet.likes) if updated_tweet else 0} likes"
    )

    if updated_tweet and updated_tweet.likes is not None:
        likes_list = [
            schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
            for like in updated_tweet.likes
        ]
        attachments_list = [f"/media/{Path(media.file_path).name}" for media in updated_tweet.media]
        tweet_out = schemas.TweetOut(
            id=updated_tweet.id,
            content=updated_tweet.content,
            created_at=updated_tweet.created_at,
            author=schemas.UserInTweet.model_validate(updated_tweet.author),
            attachments=attachments_list,
            likes=likes_list,
        )
        logger.info(
            f"[UNLIKE] SUCCESS: Returning updated tweet with {len(likes_list)} likes"
        )
        return {"result": True, "tweet": tweet_out}

    logger.warning("[UNLIKE] WARNING: Tweet not found after unlike")
    return {"result": True}


@router.get("/api/tweets", response_model=schemas.TweetListResponse)
async def get_tweet_feed(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Эндпоинт получения ленты твитов с кешированием.
    """
    r = await get_redis()
    cache_key = f"feed:{user.id}"

    # 1. Пробуем достать из кеша
    cached_data = await r.get(cache_key)
    if cached_data:
        logger.info(f"Cache HIT for user {user.id}")
        return schemas.TweetListResponse.model_validate_json(cached_data)

    logger.info(f"Cache MISS for user {user.id}. Querying DB...")

    # 2. Если нет — идем в БД
    tweets_orm = await crud.get_feed(db, user.id)

    tweets_list = []
    for tweet in tweets_orm:
        likes_list = [
            schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
            for like in tweet.likes
        ]
        attachments_list = [f"/media/{Path(media.file_path).name}" for media in tweet.media]

        tweet_out = schemas.TweetOut(
            id=tweet.id,
            content=tweet.content,
            created_at=tweet.created_at,
            author=schemas.UserInTweet.model_validate(tweet.author),
            attachments=attachments_list,
            likes=likes_list,
        )
        tweets_list.append(tweet_out)

    response_obj = schemas.TweetListResponse(tweets=tweets_list)

    # 3. Сохраняем в кэш на 60 секунд
    await r.set(cache_key, response_obj.model_dump_json(), ex=60)
    logger.info(f"Feed for user {user.id} cached for 60s")

    return response_obj
