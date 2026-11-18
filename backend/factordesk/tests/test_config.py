from pathlib import Path

import pytest

from factordesk.config import Settings


def test_settings_defaults_load(monkeypatch: pytest.MonkeyPatch) -> None:
    # Ignore any real environment values so the defaults themselves are what is tested.
    for name in ("ALPACA_API_KEY", "ALPACA_SECRET_KEY", "ALPACA_DATA_FEED", "DATA_DIR"):
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.alpaca_api_key == ""
    assert settings.alpaca_secret_key == ""
    assert settings.alpaca_data_feed == "iex"
    assert settings.data_dir == Path("data")
