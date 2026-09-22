from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # hide_input_in_errors: a missing-variable error must not echo the other
    # settings' values (secret_key, the password inside database_url) into logs.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", hide_input_in_errors=True
    )

    database_url: SecretStr
    redis_url: str
    environment: str = "development"
    pool_max_overflow: int = 10
    pool_size: int = 5
    pool_recycle: int = 3600

@lru_cache
def get_settings() -> Settings:
    return Settings()