from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database import get_db
from services.users.app import crud, schemas
from services.users.app.models import User

router = APIRouter()


# --- Зависимость для авторизации ---
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Header(alias="api-key")] = None,
) -> User:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")

    user = await crud.get_user_by_api_key(db, api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return user


# --- Эндпоинты ---


@router.get("/api/users/me", response_model=schemas.UserOut)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.UserOut:
    # Обновляем данные пользователя с загрузкой связей
    full_user = await crud.get_user_by_id(db, user.id)

    # Явно валидируем и преобразуем User -> UserResponse
    user_response = schemas.UserResponse.model_validate(full_user)
    return schemas.UserOut(user=user_response)


@router.get("/api/users/{user_id}", response_model=schemas.UserOut)
async def get_user_profile(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> Any:
    user = await crud.get_user_by_id(db, user_id)
    if not user:
        # Возвращаем словарь, FastAPI сам превратит его в JSON
        return {
            "result": False,
            "error_type": "NotFoundError",
            "error_message": "User not found",
        }

    # Явно валидируем User -> UserResponse
    user_response = schemas.UserResponse.model_validate(user)
    return schemas.UserOut(user=user_response)


@router.post("/api/users/{user_id}/follow")
async def follow_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    success = await crud.follow_user(db, current_user.id, user_id)

    if not success:
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Cannot follow user (already following or self-follow)",
        }

    return {"result": True}


@router.delete("/api/users/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    success = await crud.unfollow_user(db, current_user.id, user_id)

    if not success:
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Not following this user",
        }

    return {"result": True}
