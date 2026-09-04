"""Run server.main() with --once end to end.

Everything external is replaced: the Google API with a stub, the weather
service with the registered mock, Chromium with a fake renderer, and the
views' output dirs with a temp dir. What is left is exactly the wiring in
main(): config -> validate -> pages -> source -> DisplayServer.run(once).
"""
import logging.config
import sys

import pytest
import yaml
from PIL import Image

import server
import views.page


class StubGoogle:
    def __init__(self, key):
        self.key = key

    def get_static_map_local_src(self, map_id, location):
        return f"map-cache/staticmap_{map_id}_{location}.png"


class FakeRenderer:
    def __init__(self, *a, **k):
        pass

    def render(self, html_path, width, height):
        return Image.new("RGB", (width, height), (180, 180, 180))


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    config = {
        "server": {"port": 8080, "timezone": "Europe/Dublin"},   # --once never binds it
        "display": {"pools": {"today": ["today.png"], "tomorrow": ["tomorrow.png"]},
                    "schedule": {"type": "times", "08:00:00": "today", "20:00:00": "tomorrow"}},
        "weather": {"service": "mock", "num_hourly_forecasts": 6},
        "google": {"apikey": "G", "staticmaps_mapid": "M"},
        "location": "Dublin",
        "image": {"width": 200, "height": 300},
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config))
    (tmp_path / "version.json").write_text('{"version": "vtest"}')

    monkeypatch.setattr(server, "cwd", str(tmp_path))
    monkeypatch.setattr(server, "GoogleAPIService", StubGoogle)
    monkeypatch.setattr(logging.config, "fileConfig", lambda *a, **k: None)
    monkeypatch.setattr("epd_server.page.ChromiumRenderer", FakeRenderer)
    monkeypatch.setattr(views.page, "HTML_DIR", str(tmp_path / "html"))
    monkeypatch.setattr(views.page, "PNG_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(sys, "argv", ["server.py", "--once"])
    return tmp_path


def test_main_once_renders_every_page_and_exits(project_dir, caplog):
    caplog.set_level(logging.INFO)
    server.main()

    out = project_dir / "out"
    for name in ("today", "current", "hourly", "daily", "tomorrow"):
        assert (out / f"{name}.png").exists(), f"{name}.png not written"
        assert (project_dir / "html" / f"{name}.html").exists()
        img = Image.open(out / f"{name}.png")
        assert img.size == (200, 300) and img.mode == "L"

    assert "Inkplate Weather Calendar Server version: vtest" in caplog.text
    assert "once: images generated, not starting the server" in caplog.text


def test_main_exits_on_bad_config(project_dir, caplog):
    cfg = yaml.safe_load((project_dir / "config.yaml").read_text())
    cfg["display"] = {"pools": {"nope": ["nope.png"]}, "schedule": {"type": "times", "08:00:00": "nope"}}
    (project_dir / "config.yaml").write_text(yaml.safe_dump(cfg))
    # A schedule naming a page that does not exist is caught by DisplayServer
    # at construction, before anything is rendered, and reported like any
    # other config error.
    with pytest.raises(SystemExit):
        server.main()
    assert "display.schedule names ['nope.png']" in caplog.text
    assert not (project_dir / "out").exists()
