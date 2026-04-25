import logging
import random
from argparse import ArgumentParser
from typing import Callable

from locust import between, events, task
from locust.contrib.fasthttp import FastHttpUser

logger = logging.getLogger(__name__)


@events.init_command_line_parser.add_listener
def on_parser(parser: ArgumentParser) -> None:
    """Добавляем кастомный параметр --api-key для Locust."""
    parser.add_argument(
        "--api-key",
        default="test",
        help="API key для аутентификации (по умолчанию: test — пользователь из seed_db)",
    )


class TwitterUser(FastHttpUser):
    wait_time: Callable[..., float] = between(0.1, 0.5)

    def on_start(self) -> None:
        """Проверить api-key и авторизоваться."""
        self.api_key = self.environment.parsed_options.api_key
        self.headers = {"api-key": self.api_key}

        # Проверяем, что api-key работает
        resp = self.client.get(
            "/api/users/me",
            headers=self.headers,
            name="/api/users/me [auth-check]",
        )
        if resp.status_code == 401:
            logger.error(
                "❌ API key '%s' не найден в БД. "
                "Запустите seed_db.py чтобы создать тестового пользователя:\n"
                "  kubectl run seed-db --namespace=twitter-clone "
                "--image=twitter-clone-2026:latest --restart=Never "
                "--env-from=configmap/app-config --env-from=secret/db-credentials "
                "-- python -m scripts.seed_db",
                self.api_key,
            )
        elif resp.status_code == 200:
            logger.info("✅ Аутентификация успешна (api-key: %s)", self.api_key)

    @task(3)
    def view_feed(self) -> None:
        """View feed (most frequent action)."""
        self.client.get("/api/tweets", headers=self.headers, name="/api/tweets [GET]")

    @task(1)
    def create_tweet(self) -> None:
        """Create a tweet."""
        payload = {
            "tweet_data": f"Load test tweet {random.randint(0, 10000)}",
            "tweet_media_ids": [],
        }
        self.client.post(
            "/api/tweets", json=payload, headers=self.headers, name="/api/tweets [POST]"
        )

    @task(2)
    def view_profile(self) -> None:
        """View profile."""
        self.client.get("/api/users/me", headers=self.headers, name="/api/users/me")
