import random
from typing import Callable

from locust import between, task
from locust.contrib.fasthttp import FastHttpUser


class TwitterUser(FastHttpUser):
    wait_time: Callable[..., float] = between(0.1, 0.5)

    def on_start(self) -> None:
        """Actions on start: Get API Key."""
        # Our test DB has a user with key 'test'
        self.api_key = "test"
        self.headers = {"api-key": self.api_key}

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
