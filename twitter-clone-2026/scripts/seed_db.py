import asyncio
import os
import random
import sys
from datetime import datetime, timedelta, timezone  # Добавили timedelta

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
    """Очистка таблиц перед заполнением."""
    print("Clearing database...")
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

    test_user = User(name="Valera", api_key="test")
    users.append(test_user)

    for _ in range(NUM_USERS - 1):
        user = User(name=fake.user_name(), api_key=fake.uuid4())
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
        num_follows = random.randint(0, MAX_FOLLOWS_PER_USER)
        potential_followees = [u for u in users if u.id != user.id]
        if not potential_followees:
            continue

        followees = random.sample(
            potential_followees, min(num_follows, len(potential_followees))
        )
        for followee in followees:
            follows.append(Follower(follower_id=user.id, followed_id=followee.id))

    db.add_all(follows)
    await db.commit()
    print(f"Created {len(follows)} follows.")


async def seed_tweets(db: AsyncSession, users: list[User]) -> list[Tweet]:
    """Создание твитов с РАЗНЫМ временем (разброс по часам/дням)."""
    print("Creating tweets with staggered time...")
    tweets = []

    # Берем текущее время как точку отсчета
    now = datetime.now(timezone.utc)

    for user in users:
        num_tweets = random.randint(0, MAX_TWEETS_PER_USER)
        for _ in range(num_tweets):
            # === ЛОГИКА ВРЕМЕНИ ===
            # Случайный сдвиг: от 5 минут до 7 дней назад
            # Это создаст красивый разброс: "5 мин назад", "2 часа назад", "вчера"
            delta = timedelta(
                days=random.randint(0, 6),
                hours=random.randint(0, 23),
                minutes=random.randint(1, 59),
            )
            post_time = now - delta

            tweet = Tweet(
                content=fake.sentence(nb_words=random.randint(5, 20)),
                author_id=user.id,
                created_at=post_time,  # Явно передаем время
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
        return

    for user in users:
        num_likes = random.randint(0, MAX_LIKES_PER_USER)
        liked_tweets = random.sample(tweets, min(num_likes, len(tweets)))
        for tweet in liked_tweets:
            likes.append(Like(user_id=user.id, tweet_id=tweet.id))

    db.add_all(likes)
    await db.commit()
    print(f"Created {len(likes)} likes.")


async def main() -> None:
    async with AsyncSessionLocal() as db:
        await clear_db(db)
        users = await seed_users(db)
        await seed_follows(db, users)
        tweets = await seed_tweets(db, users)
        await seed_likes(db, users, tweets)

    print("\n=== Database Seeding Complete! ===")


if __name__ == "__main__":
    asyncio.run(main())
