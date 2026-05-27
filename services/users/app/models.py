import secrets
from hashlib import sha256
from typing import TYPE_CHECKING, List

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database import Base

if TYPE_CHECKING:
    from services.tweets.app.models import Like, Tweet


class User(Base):
    """
    User model with secure API key hashing.
    ✅ FIXED: API ключи хешируются с SHA256
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)

    # ✅ NEW: Хеш API ключа вместо plain text
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

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
    tweets: Mapped[List["Tweet"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

    # Связь с лайками пользователя
    likes: Mapped[List["Like"]] = relationship(back_populates="user", cascade="delete")

    # ============================================================
    # STATIC METHODS FOR SECURE API KEY HANDLING
    # ============================================================

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key using SHA256."""
        return sha256(api_key.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_api_key() -> str:
        """Generate a new secure API key."""
        return secrets.token_urlsafe(32)

    def verify_api_key(self, api_key: str) -> bool:
        """Verify if a provided API key matches the stored hash."""
        provided_hash = self.hash_api_key(api_key)
        return provided_hash == self.api_key_hash


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
    __table_args__ = (
        UniqueConstraint("follower_id", "followed_id", name="unique_follow"),
    )
