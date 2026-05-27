from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with security-conscious defaults.
    ✅ FIXED: Added CORS and logging configuration
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Kafka
    kafka_bootstrap_servers: str = "kafka:9092"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Security
    secret_key: str

    # ✅ NEW: CORS Configuration
    allowed_origins: str = "http://localhost:3000"  # CSV list
    cors_allow_credentials: bool = False
    cors_allow_methods: str = "GET,POST,DELETE"
    cors_allow_headers: str = "api-key,content-type,accept"
    cors_max_age: int = 3600

    # ✅ NEW: Logging configuration
    sqlalchemy_echo: bool = False  # NEVER echo in production!
    log_api_keys: bool = False  # NEVER log API keys!

    @property
    def sqlalchemy_database_url(self) -> str:
        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/"
            f"{self.postgres_db}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CSV origins into list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def cors_methods_list(self) -> list[str]:
        """Parse CSV methods into list."""
        return [m.strip() for m in self.cors_allow_methods.split(",") if m.strip()]

    @property
    def cors_headers_list(self) -> list[str]:
        """Parse CSV headers into list."""
        return [h.strip() for h in self.cors_allow_headers.split(",") if h.strip()]


settings = Settings()
