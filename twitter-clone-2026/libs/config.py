from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс настроек приложения.
    Автоматически читает переменные окружения из файла .env.
    """

    # Настройки базы данных PostgreSQL
    # Field(...) означает, что поле обязательное
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")

    # Настройки Kafka
    kafka_url: str = Field(default="kafka:9092", alias="KAFKA_URL")

    # Настройки Redis
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")

    # Настройки безопасности

    secret_key: str = Field(..., alias="SECRET_KEY")

    # Конфигурация Pydantic для работы с .env файлом
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Игнорировать лишние переменные в .env
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Собирает строку подключения (DSN) для SQLAlchemy + asyncpg.
        Пример: postgresql+asyncpg://user:password@localhost:5432/db
        """
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/"
            f"{self.postgres_db}"
        )


# Создаем глобальный экземпляр настроек.
# Теперь в любом месте кода можно сделать: from libs.config import settings
settings = Settings()
