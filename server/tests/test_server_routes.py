"""Tests for Flask route handlers — verify X-Next-URL and X-Next-Refresh-Seconds headers."""
import pytest
from zoneinfo import ZoneInfo

import server


@pytest.fixture(autouse=True)
def setup_server_globals(monkeypatch):
    """Provide the minimal globals get_next_wake() needs."""
    monkeypatch.setattr(server, "server_display_schedule", [("09:00:00", "today.png")])
    monkeypatch.setattr(server, "server_tz", ZoneInfo("UTC"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with fake PNG files on disk."""
    views = tmp_path / "views"
    views.mkdir()
    (views / "today.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (views / "daily.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(server, "cwd", str(tmp_path))

    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def test_today_png_x_next_url_present(client):
    rsp = client.get("/today.png")
    assert rsp.status_code == 200
    assert rsp.headers["X-Next-URL"].startswith("http://localhost/")


def test_daily_png_x_next_url_present(client):
    rsp = client.get("/daily.png")
    assert rsp.status_code == 200
    assert rsp.headers["X-Next-URL"].startswith("http://localhost/")


def test_x_next_refresh_seconds_present(client):
    rsp = client.get("/today.png")
    assert rsp.status_code == 200
    assert "X-Next-Refresh-Seconds" in rsp.headers
    assert int(rsp.headers["X-Next-Refresh-Seconds"]) >= 0


def test_missing_file_returns_404(tmp_path, monkeypatch):
    views = tmp_path / "views"
    views.mkdir()
    # today.png deliberately not created; daily.png present for daily route
    (views / "daily.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(server, "cwd", str(tmp_path))

    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        rsp = c.get("/today.png")
    assert rsp.status_code == 404
