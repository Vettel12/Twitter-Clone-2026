from libs.database import Base
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
if TYPE_CHECKING:
    from services.tweets.app.models import Tweet, Like


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)

    # Кто подписан на меня (список объектов User)
    followers: Mapped[List["User"]] = relationship(
        "User",
        secondary="followers",
        primaryjoin="User.id == Follower.followed_id",
        secondaryjoin="User.id == Follower.follower_id",
        back_populates="following",
        viewonly=True,
    )

    # На кого я подписан (список объектов User)
    following: Mapped[List["User"]] = relationship(
        "User",
        secondary="followers",
        primaryjoin="User.id == Follower.follower_id",
        secondaryjoin="User.id == Follower.followed_id",
        back_populates="followers",
        viewonly=True,
    )

    # Связь с твитами пользователя
    tweets: Mapped[List["Tweet"]] = relationship(back_populates="author")

    # Связь с лайками пользователя
    likes: Mapped[List["Like"]] = relationship(back_populates="user")


class Follower(Base):
    """
    Ассоциативная таблица для связи Многие-ко-Многим.
    Здесь мы храним сами связи.
    """
    __tablename__ = "followers"

    # Составной первичный ключ из follower_id и followed_id
    follower_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    followed_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)

    # Уникальное ограничение, чтобы один пользователь не мог подписаться на другого более одного раза
    __table_args__ = (UniqueConstraint('follower_id', 'followed_id', name='unique_follow'),)
