from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс настроек приложения.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Pydantic-settings АВТОМАТИЧЕСКИ найдет переменную POSTGRES_USER
    # (приводит имя поля к верхнему регистру)
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Настройки Kafka
    kafka_url: str = "kafka:9092"

    # Настройки Redis
    redis_url: str = "redis://redis:6379/0"

    # Безопасность
    secret_key: str

    @property
    def sqlalchemy_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/"
            f"{self.postgres_db}"
        )


settings = Settings()
