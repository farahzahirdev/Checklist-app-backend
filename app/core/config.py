from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Checklist App API", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    db_host: str = Field(default="localhost", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_name: str = Field(default="ckecklist", alias="DB_NAME")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="password", alias="DB_PASSWORD")
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_currency: str = Field(default="USD", alias="STRIPE_CURRENCY")
    stripe_default_amount_cents: int = Field(default=4900, alias="STRIPE_DEFAULT_AMOUNT_CENTS")
    auth_secret_key: str = Field(default="dev-auth-secret-change-me", alias="AUTH_SECRET_KEY")
    auth_token_ttl_minutes: int = Field(default=720, alias="AUTH_TOKEN_TTL_MINUTES")
    mfa_secret_token_ttl_minutes: int = Field(default=15, alias="MFA_SECRET_TOKEN_TTL_MINUTES")
    access_unlock_days: int = Field(default=30, alias="ACCESS_UNLOCK_DAYS")
    assessment_completion_days: int = Field(default=7, alias="ASSESSMENT_COMPLETION_DAYS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache

def get_settings() -> Settings:
    return Settings()
