from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database import Base

# Импортируем модель User, чтобы SQLAlchemy понимал связь
if TYPE_CHECKING:
    from services.users.app.models import User


class Tweet(Base):
    """
    Модель твита (поста).
    """

    __tablename__ = "tweets"

    # Уникальный идентификатор твита
    id: Mapped[int] = mapped_column(primary_key=True)

    # Текст твита. Используем Text, так как длина может превышать 255 символов
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ID автора, ссылка на таблицу users
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # Автоматическая установка времени создания при добавлении в БД
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Автоматическое обновление времени при изменении записи
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Связь с объектом автора. back_populates указывает на поле "tweets" в модели User
    author: Mapped["User"] = relationship(back_populates="tweets")

    # Связь с картинками. Один твит может иметь много картинок
    media: Mapped[List["Media"]] = relationship(back_populates="tweet", lazy="selectin")

    # Связь с лайками. Один твит может иметь много лайков
    likes: Mapped[List["Like"]] = relationship(back_populates="tweet", lazy="selectin")


class Media(Base):
    """
    Модель медиа-файлов (изображений).
    """

    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Путь к файлу на диске или ссылка
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)

    # ID твита, к которому привязан файл.
    # Optional и nullable=True: так как ТЗ требует сначала загрузить файл (POST /medias),
    # а только потом создать твит. В момент загрузки твита еще не существует.
    tweet_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tweets.id"), nullable=True, default=None
    )

    # Обратная связь к твиту
    tweet: Mapped[Optional["Tweet"]] = relationship(back_populates="media")


class Like(Base):
    """
    Модель лайка (связь пользователь-твит).
    """

    __tablename__ = "likes"

    # Составной первичный ключ.
    # Это гарантирует, что один пользователь не может поставить два лайка одному твиту.
    # user_id и tweet_id вместе составляют уникальную запись.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tweet_id: Mapped[int] = mapped_column(ForeignKey("tweets.id"), primary_key=True)

    # Связь с пользователем, который поставил лайк. back_populates="likes" в модели User
    user: Mapped["User"] = relationship(back_populates="likes")

    # Связь с твитом, который лайкнули
    tweet: Mapped["Tweet"] = relationship(back_populates="likes")
