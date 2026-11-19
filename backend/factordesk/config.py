from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_data_feed: str = "iex"
    data_dir: Path = Path("data")

    # Multi-ticker price downloads (YFinanceProvider.fetch_many). Yahoo publishes no rate limit,
    # so the defaults are deliberately gentle (wiki/decision-parallel-throttled-price-downloads.md).
    price_chunk_size: int = Field(default=5, ge=1, le=50)  # tickers per chunk
    price_max_workers: int = Field(default=3, ge=1, le=8)  # chunks downloaded at once
    price_min_interval_seconds: float = Field(default=0.5, ge=0.0, le=30.0)  # between starts
    price_max_attempts: int = Field(default=3, ge=1, le=6)  # tries per ticker
    price_breaker_threshold: int = Field(default=3, ge=1, le=20)  # rate limits in a row


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
