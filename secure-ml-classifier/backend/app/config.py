from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    environment: str = "development"
    secret_key: str = "dev-only-insecure-secret-change-me"  # noqa: S105 - refused in production
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    jwt_algorithm: str = "HS256"

    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'app.db'}"
    storage_dir: Path = BASE_DIR / "data" / "storage"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_upload_bytes: int = 25 * 1024 * 1024
    max_rows: int = 200_000
    max_columns: int = 200

    login_rate_limit: str = "10/minute"
    train_rate_limit: str = "20/hour"
    default_rate_limit: str = "240/minute"

    password_min_length: int = 12
    max_failed_logins: int = 5
    lockout_minutes: int = 15

    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "ChangeMe!Admin123"  # noqa: S105 - seed only, rotate on first login

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
    return settings
