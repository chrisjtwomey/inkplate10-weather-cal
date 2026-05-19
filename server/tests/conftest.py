"""Shared fixtures for the server test suite."""
import pathlib

import pytest


FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"

_ACCUWEATHER_CACHE = (
    pathlib.Path(__file__).parent.parent
    / "weather" / "accuweather" / ".cache.json"
)


@pytest.fixture(autouse=True)
def clear_accuweather_cache():
    """Delete the AccuWeather disk cache before and after every test so cached
    responses from one test never bleed into another."""
    _ACCUWEATHER_CACHE.unlink(missing_ok=True)
    yield
    _ACCUWEATHER_CACHE.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """
    Strip env vars our config resolver consults so each test starts clean.
    Individual tests opt back in via `monkeypatch.setenv(...)`.
    """
    for prefix in ("WEATHER_", "GOOGLE_", "SERVER_", "MQTT_", "IMAGE_"):
        for key in list(__import__("os").environ):
            if key.startswith(prefix):
                monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("LOCATION", raising=False)
    monkeypatch.delenv("DEBUG", raising=False)


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR
