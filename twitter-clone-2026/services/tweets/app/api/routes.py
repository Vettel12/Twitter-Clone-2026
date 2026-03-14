from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from libs.database import get_db
from services.users.app.crud import get_user_by_api_key
from services.users.app.models import User
from services.tweets.app import crud, schemas

router = APIRouter()

# --- Зависимость для авторизации (повторяем логику из users) ---
async def get_current_user(
    api_key: Optional[str] = Header(None, alias="api-key"),
    db: AsyncSession = Depends(get_db)
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
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузка картинки.
    """
    media_id = await crud.save_media(db, file)
    return schemas.MediaUploadResponse(media_id=media_id)


@router.post("/api/tweets", response_model=schemas.TweetCreateResponse)
async def create_tweet(
    tweet_data: schemas.TweetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Создание твита.
    """
    tweet_id = await crud.create_tweet(
        db, 
        author_id=user.id, 
        content=tweet_data.tweet_data, 
        media_ids=tweet_data.tweet_media_ids
    )
    return schemas.TweetCreateResponse(tweet_id=tweet_id)


@router.delete("/api/tweets/{tweet_id}")
async def delete_tweet(
    tweet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удаление твита. Только автор может удалять.
    """
    try:
        success = await crud.delete_tweet(db, user.id, tweet_id)
        if not success:
            return {"result": False, "error_message": "Tweet not found"}
        return {"result": True}
    except PermissionError as e:
        # Ловим ошибку прав доступа из CRUD
        return {"result": False, "error_message": str(e)}
    

@router.post("/api/tweets/{tweet_id}/likes")
async def like_tweet(
    tweet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Поставить лайк.
    """
    success = await crud.add_like(db, user.id, tweet_id)
    if not success:
        return {"result": False, "error_message": "Cannot like tweet (already liked or not found)"}
    return {"result": True}


@router.delete("/api/tweets/{tweet_id}/likes")
async def unlike_tweet(
    tweet_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Убрать лайк.
    """
    success = await crud.remove_like(db, user.id, tweet_id)
    if not success:
        return {"result": False, "error_message": "Like not found"}
    return {"result": True}
