from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Primary persistence (PostgreSQL). Async sqlalchemy_url form:
    #   postgresql+asyncpg://user:pass@host:5432/dbname
    DATABASE_URL: str
    SQLA_ECHO: bool = False

    # Legacy MongoDB connection — kept optional for the migration window.
    # The runtime uses Postgres by default; Mongo is only read by the
    # migration script `scripts/migrate_mongo_to_postgres.py`.
    MONGO_URI: str | None = None
    MONGO_DB: str | None = None
    MONGO_RETAIN: bool = False  # set True to keep the Mongo lifespan active

    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 8
    PORT: int = 5000
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["*"]

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_DEFAULT: str = "20/minute"
    RATE_LIMIT_LOGIN: str = "10/minute"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def validate_secrets(self) -> None:
        if not self.DATABASE_URL:
            raise ValueError("DATABASE_URL must be set in .env (postgresql+asyncpg://...)")
        if not self.DATABASE_URL.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL DSN (postgresql+asyncpg://...)")
        if not self.JWT_SECRET or len(self.JWT_SECRET) < 16:
            raise ValueError("JWT_SECRET must be set and be at least 16 characters in .env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
