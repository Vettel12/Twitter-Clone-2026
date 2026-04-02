import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database import get_db
from services.users.app import crud, schemas
from services.users.app.models import User

# Настройка логирования
logger = logging.getLogger(__name__)

router = APIRouter()


# --- Зависимость для авторизации ---
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Header(alias="api-key")] = None,
) -> User:
    if not api_key:
        logger.warning("Authentication failed: Missing API Key")
        raise HTTPException(status_code=401, detail="Missing API Key")

    user = await crud.get_user_by_api_key(db, api_key)
    if not user:
        logger.warning(f"Authentication failed: Invalid API Key '{api_key[:4]}...'")
        raise HTTPException(status_code=401, detail="Invalid API Key")

    logger.info(f"User authenticated: id={user.id}, name={user.name}")
    return user


# --- Эндпоинты ---


@router.get("/api/users/me", response_model=schemas.UserOut)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.UserOut:
    logger.info(f"User {user.id} requested their profile")

    full_user = await crud.get_user_by_id(db, user.id)
    user_response = schemas.UserResponse.model_validate(full_user)

    logger.debug(f"User {user.id} profile data prepared")
    return schemas.UserOut(user=user_response)


@router.get("/api/users/{user_id}")
async def get_user_profile(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> Any:
    logger.info(f"Request for user profile id={user_id}")

    user = await crud.get_user_by_id(db, user_id)
    if not user:
        logger.warning(f"User profile id={user_id} not found")
        return {
            "result": False,
            "error_type": "NotFoundError",
            "error_message": "User not found",
        }

    user_response = schemas.UserResponse.model_validate(user)
    logger.info(f"User profile id={user_id} found: {user.name}")
    return schemas.UserOut(user=user_response)


@router.post("/api/users/{user_id}/follow")
async def follow_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    logger.info(f"User {current_user.id} attempting to follow {user_id}")

    success = await crud.follow_user(db, current_user.id, user_id)

    if not success:
        logger.warning(
            f"Follow failed: User {current_user.id} -> {user_id} (already following or self)"
        )
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Cannot follow user (already following or self-follow)",
        }

    logger.info(f"User {current_user.id} successfully followed {user_id}")
    return {"result": True}


@router.delete("/api/users/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    logger.info(f"User {current_user.id} attempting to unfollow {user_id}")

    success = await crud.unfollow_user(db, current_user.id, user_id)

    if not success:
        logger.warning(
            f"Unfollow failed: User {current_user.id} -> {user_id} (not following)"
        )
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Not following this user",
        }

    logger.info(f"User {current_user.id} successfully unfollowed {user_id}")
    return {"result": True}
