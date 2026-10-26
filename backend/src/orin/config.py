"""Runtime settings, read from environment variables and `.env`."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    meta_api_base_url: str = "https://api.meta.ai/v1"
    model_api_key: SecretStr | None = None
    # Standard by default so real data is never shared; set the -contributor ID for dev/demo.
    router_model: str = "muse-spark-1.3"
    router_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "minimal"
    image_model: str = "muse-image-1.0"

    # Open-weights hosts, tried in this order (see `open_weights_hosts`).
    baseten_base_url: str | None = None
    baseten_api_key: SecretStr | None = None
    baseten_model: str = "meta-models/muse-spark-open-1026"
    modal_base_url: str | None = None
    modal_api_key: SecretStr | None = None
    modal_model: str = "meta-models/muse-spark-open-1026"
    open_weights_order: str = "baseten,modal"

    # "spark": best fit → Muse Spark → Muse Spark Open. "free": best fit → Muse Spark Open.
    orin_route_fallback: Literal["spark", "free"] = "spark"

    orin_owner_token: SecretStr | None = None
    orin_data_dir: Path = Path("data")

    @property
    def database_path(self) -> Path:
        return self.orin_data_dir / "orin.db"

    @property
    def images_dir(self) -> Path:
        return self.orin_data_dir / "images"


@lru_cache
def get_settings() -> Settings:
    return Settings()
