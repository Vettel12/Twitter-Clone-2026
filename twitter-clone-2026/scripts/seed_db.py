import asyncio
import os
import random
import sys

from faker import Faker
from sqlalchemy import delete

# Добавляем корень проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import AsyncSession

from libs.database import AsyncSessionLocal
from services.tweets.app.models import Like, Media, Tweet
from services.users.app.models import Follower, User

# Инициализация Faker
fake = Faker("ru_RU")

# Конфигурация количества данных
NUM_USERS = 50
MAX_TWEETS_PER_USER = 10
MAX_FOLLOWS_PER_USER = 10
MAX_LIKES_PER_USER = 15


async def clear_db(db: AsyncSession) -> None:
    """Очистка таблиц перед заполнением (осторожно в проде!)."""
    print("Clearing database...")
    # Удаляем в порядке зависимостей
    await db.execute(delete(Like))
    await db.execute(delete(Media))
    await db.execute(delete(Tweet))
    await db.execute(delete(Follower))
    await db.execute(delete(User))
    await db.commit()
    print("Database cleared.")


async def seed_users(db: AsyncSession) -> list[User]:
    """Создание пользователей."""
    print(f"Creating {NUM_USERS} users...")
    users = []

    # Создаем гарантированного пользователя для тестов
    test_user = User(name="Valera", api_key="test")
    users.append(test_user)

    # Создаем остальных через Faker
    for _ in range(NUM_USERS - 1):
        user = User(
            name=fake.user_name(),  # Генерирует имя типа "ivan_petrov"
            api_key=fake.uuid4(),  # Генерирует уникальный ключ
        )
        users.append(user)

    db.add_all(users)
    await db.commit()
    print(f"Created {len(users)} users.")
    return users


async def seed_follows(db: AsyncSession, users: list[User]) -> None:
    """Создание подписок."""
    print("Creating follows...")
    follows = []

    for user in users:
        # Выбираем случайных пользователей для подписки (кроме себя)
        num_follows = random.randint(0, MAX_FOLLOWS_PER_USER)
        followees = random.sample([u for u in users if u.id != user.id], num_follows)

        for followee in followees:
            follow = Follower(follower_id=user.id, followed_id=followee.id)
            follows.append(follow)

    db.add_all(follows)
    await db.commit()
    print(f"Created {len(follows)} follows.")


async def seed_tweets(db: AsyncSession, users: list[User]) -> list[Tweet]:
    """Создание твитов."""
    print("Creating tweets...")
    tweets = []

    for user in users:
        num_tweets = random.randint(0, MAX_TWEETS_PER_USER)
        for _ in range(num_tweets):
            tweet = Tweet(
                content=fake.sentence(nb_words=random.randint(5, 20)), author_id=user.id
            )
            tweets.append(tweet)

    db.add_all(tweets)
    await db.commit()
    print(f"Created {len(tweets)} tweets.")
    return tweets


async def seed_likes(db: AsyncSession, users: list[User], tweets: list[Tweet]) -> None:
    """Создание лайков."""
    print("Creating likes...")
    likes = []

    if not tweets:
        print("No tweets to like.")
        return

    for user in users:
        num_likes = random.randint(0, MAX_LIKES_PER_USER)
        # Выбираем случайные твиты
        liked_tweets = random.sample(tweets, min(num_likes, len(tweets)))

        for tweet in liked_tweets:
            like = Like(user_id=user.id, tweet_id=tweet.id)
            likes.append(like)

    db.add_all(likes)
    await db.commit()
    print(f"Created {len(likes)} likes.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Очистка
        await clear_db(db)

        # 2. Генерация данных
        users = await seed_users(db)
        await seed_follows(db, users)
        tweets = await seed_tweets(db, users)
        await seed_likes(db, users, tweets)

    print("\n=== Database Seeding Complete! ===")
    print(f"Users: {NUM_USERS}")
    print("Test user credentials: api-key='test', name='Valera'")


if __name__ == "__main__":
    asyncio.run(main())
