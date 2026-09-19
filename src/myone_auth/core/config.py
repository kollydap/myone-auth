from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr
    redis_url: str
    secret_key: SecretStr
    environment: str = "development"
    pool_max_overflow: int = 10
    pool_size: int = 5
    pool_recycle: int = 3600

@lru_cache
def get_settings() -> Settings:
    return Settings()