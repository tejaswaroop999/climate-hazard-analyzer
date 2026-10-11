from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_database: str = "climate"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    cache_ttl_days: int = Field(default=30, ge=1, le=365)
    rate_limit_per_minute: int = Field(default=20, ge=1, le=1000)
    # Search is cheap and fires while typing, so it gets its own, larger budget.
    search_rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    # Number of trusted reverse proxies that append to X-Forwarded-For.
    # 0 = use the socket address. Render/nginx = 1. Never trust more than exist.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)


@lru_cache
def get_settings() -> Settings:
    return Settings()
