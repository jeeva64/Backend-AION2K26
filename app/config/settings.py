from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    MONGO_URI: str
    MONGO_DB: str | None = None
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
        if not self.MONGO_URI:
            raise ValueError("MONGO_URI must be set in .env")
        if not self.JWT_SECRET or len(self.JWT_SECRET) < 16:
            raise ValueError("JWT_SECRET must be set and be at least 16 characters in .env")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
