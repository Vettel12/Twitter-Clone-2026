from pydantic import BaseModel, Field, ConfigDict
from typing import List


# 1. Базовая схема (для отображения в списках, например, в лайках или подписчиках)
class UserBase(BaseModel):
    id: int = Field(..., description="ID пользователя", examples=[1])
    name: str = Field(..., description="Имя пользователя", examples=["John Doe"])


    # Настройка для совместимости с SQLAlchemy моделями
    model_config = ConfigDict(from_attributes=True)


# 2. Схема для ответа профиля (с подписчиками и подписками)
class UserResponse(UserBase):
    """
    Полный профиль пользователя.
    Наследует id и name от UserBase, добавляет связи.
    """
    followers: List["UserBase"] = Field(
        default_factory=list, 
        description="Список подписчиков"
    )
    following: List["UserBase"] = Field(
        default_factory=list, 
        description="Список подписок"
    )


# 3. Обертка для ответа API
class UserOut(BaseModel):
    result: bool = True
    user: UserResponse
