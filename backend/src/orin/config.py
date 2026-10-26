"""Runtime settings, read from environment variables and `.env`."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    meta_api_base_url: str = "https://api.meta.ai/v1"
    model_api_key: SecretStr | None = None
    router_model: str = "muse-spark-1.3"

    baseten_base_url: str | None = None
    baseten_api_key: SecretStr | None = None
    baseten_model: str = "meta-models/muse-spark-open-1026"

    orin_owner_token: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
