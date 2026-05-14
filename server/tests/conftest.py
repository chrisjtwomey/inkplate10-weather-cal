"""Shared fixtures for the server test suite."""
import pathlib

import pytest


FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"


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
