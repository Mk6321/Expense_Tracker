from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, loaded from environment / backend/.env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/expense_tracker"
    DATABASE_URL_MIGRATIONS: str | None = None
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 2
    DB_ECHO: bool = False

    # Auth
    JWT_SECRET: str = "insecure-dev-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE: int = 900  # seconds
    JWT_REFRESH_TOKEN_EXPIRE: int = 1209600  # seconds

    # Cookies (refresh token lives in an httpOnly cookie)
    REFRESH_COOKIE_NAME: str = "et_refresh"
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "none"
    COOKIE_DOMAIN: str | None = None

    # CORS. Kept as a raw string: pydantic-settings tries to JSON-decode any list
    # field coming from a dotenv/env source before validators run, so a plain
    # comma-separated value (what Render and .env actually carry) would explode.
    CORS_ORIGINS: str = "http://localhost:5173"

    # Domain config
    INVITE_CODE_EXPIRE_DAYS: int = 7

    # Post-MVP / server-side only
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    ENVIRONMENT: str = "development"

    @property
    def cors_origins(self) -> list[str]:
        raw = self.CORS_ORIGINS.strip()
        if raw.startswith("["):  # tolerate a JSON array too
            import json

            return [str(origin) for origin in json.loads(raw)]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def migration_database_url(self) -> str:
        return self.DATABASE_URL_MIGRATIONS or self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
