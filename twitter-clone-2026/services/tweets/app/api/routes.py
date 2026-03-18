from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database import get_db
from services.tweets.app import crud, schemas
from services.users.app.crud import get_user_by_api_key
from services.users.app.models import User

router = APIRouter()


# --- Зависимость для авторизации (повторяем логику из users) ---
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Header(alias="api-key")] = None,
) -> User:
    """
    Извлекает пользователя по заголовку api-key.
    Кидает 401 если ключа нет или он неверный.
    """
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
    """
    Загрузка картинки.
    """
    media_id = await crud.save_media(db, file)
    return schemas.MediaUploadResponse(media_id=media_id)


@router.post("/api/tweets", response_model=schemas.TweetCreateResponse)
async def create_tweet(
    tweet_data: schemas.TweetCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Создание твита.
    """
    tweet_id = await crud.create_tweet(
        db,
        author_id=user.id,
        content=tweet_data.tweet_data,
        media_ids=tweet_data.tweet_media_ids,
    )
    return schemas.TweetCreateResponse(tweet_id=tweet_id)


@router.delete("/api/tweets/{tweet_id}")
async def delete_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Удаление твита. Только автор может удалять.
    """
    try:
        success = await crud.delete_tweet(db, user.id, tweet_id)
        if not success:
            return {
                "result": False,
                "error_type": "NotFoundError",
                "error_message": "Tweet not found",
            }
        return {"result": True}
    except PermissionError as e:
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
    """
    Поставить лайк.
    """
    success = await crud.add_like(db, user.id, tweet_id)
    if not success:
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Cannot like tweet (already liked or not found)",
        }
    return {"result": True}


@router.delete("/api/tweets/{tweet_id}/likes")
async def unlike_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Убрать лайк.
    """
    success = await crud.remove_like(db, user.id, tweet_id)
    if not success:
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Like not found",
        }
    return {"result": True}


@router.get("/api/tweets", response_model=schemas.TweetListResponse)
async def get_tweet_feed(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Эндпоинт получения ленты твитов.
    """
    # 1. Получаем модели из базы
    tweets_orm = await crud.get_feed(db, user.id)

    # 2. Явно преобразуем ORM-модели в Pydantic-схемы
    tweets_list = []
    for tweet in tweets_orm:
        # Преобразуем лайки: достаем имя из связи user
        likes_list = [
            schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
            for like in tweet.likes
        ]

        # Преобразуем аттачменты: достаем путь из связи media
        attachments_list = [media.file_path for media in tweet.media]

        # Собираем объект схемы
        tweet_out = schemas.TweetOut(
            id=tweet.id,
            content=tweet.content,
            created_at=tweet.created_at,
            author=schemas.UserInTweet.model_validate(tweet.author),
            attachments=attachments_list,
            likes=likes_list,
        )
        tweets_list.append(tweet_out)

    # 3. Возвращаем ответ
    return schemas.TweetListResponse(tweets=tweets_list)
