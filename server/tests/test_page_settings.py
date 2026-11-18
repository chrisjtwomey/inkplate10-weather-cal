"""Each page's theme, photos and map, saved and applied while the server runs (page_settings.py)."""
import os
import threading
import time

import pytest
import yaml
from flask import Flask

import settings_page as sp
from page_settings import LivePages, pages_blueprint
from server import load_settings

EXAMPLE = open(os.path.join(os.path.dirname(__file__), "..", "config.example.yaml")).read()
PAGES = {"today.png", "current.png", "hourly.png", "daily.png", "tomorrow.png"}


class Page:
    def __init__(self, name, tag="old"):
        self.name, self.tag = name, tag


class FakeServer:
    def __init__(self):
        self.regen_lock = threading.Lock()
        self.pages = [Page(n) for n in ("today", "current", "hourly", "daily", "tomorrow", "tides")]
        self.redrawn = []

    def regenerate(self, only=None):
        self.redrawn.append(only)


def _text(picture=None):
    text = EXAMPLE.replace("service: accuweather\n  apikey: XXXX", "service: mock")
    if picture:
        text += "picture:\n" + "".join(f"  {page}: photos\n" for page in picture)
    return text


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "config.yaml"

    def make(picture=None, included=("a1", "b2")):
        path.write_text(_text(picture))
        cfg = load_settings(yaml.safe_load(path.read_text()))
        photo_pages = {t: None for t in cfg.page_themes if cfg.pictures[t] == "photos"}
        server = FakeServer()
        seen = []
        live = LivePages(cfg, str(path), load_settings, lambda text: sp.check_config(text, load_settings, PAGES),
                         lambda name, settings: Page(name, "new"), photo_pages, lambda: list(included),
                         server=server, on_change=seen.append)
        return live, server, photo_pages, path, seen
    return make


def _wait(server, n):
    for _ in range(100):
        if len(server.redrawn) >= n:
            return
        time.sleep(0.02)


def test_a_save_writes_only_the_pages_block_and_keeps_the_rest(setup):
    live, server, photo_pages, path, seen = setup()
    changed = live.save({"hourly": {"photos": ["a1"]}})
    text = path.read_text()
    assert changed == ["hourly"] and "# Final generated PNG width (pixels)." in text
    assert yaml.safe_load(text)["pages"] == {"hourly": {"photos": ["a1"]}}
    assert (path.parent / "config.yaml.bak").read_text() == _text()
    assert photo_pages == {"hourly": ["a1"]} and seen and seen[-1].page_photos["hourly"] == ["a1"]


def test_a_picture_size_is_saved_under_the_pages_theme_and_redraws_it(setup):
    live, server, *_ = setup()
    changed = live.save({"today": {"picture_size": 60}})
    _wait(server, 1)
    saved = yaml.safe_load(open(live.config_path).read())
    assert saved["themes"] == {"classic": {"today": {"picture_size": 60}}} and "today" not in saved.get("pages", {})
    assert changed == ["today"] and server.redrawn == ["today.png"]
    assert live.current()["today"]["picture_size"] == 60 and live.current()["current"]["picture_size"] is None


def test_a_picture_size_of_null_goes_back_to_the_themes_default(setup):
    live, server, *_ = setup()
    live.save({"today": {"picture_size": 60}})
    live.save({"today": {"picture_size": None}})
    assert "themes" not in yaml.safe_load(open(live.config_path).read())
    assert live.current()["today"]["picture_size"] is None


def test_only_the_changed_pages_are_swapped_and_redrawn(setup):
    live, server, *_ = setup()
    live.save({"today": {"photos": ["b2"]}, "daily": {"theme": "classic"}})
    _wait(server, 1)
    assert [(p.name, p.tag) for p in server.pages if p.tag == "new"] == [("today", "new")]
    assert server.redrawn == ["today.png"]
    assert [p.name for p in server.pages][-1] == "tides"


def test_changes_during_a_redraw_make_one_more_redraw_not_one_each(setup):
    live, server, *_ = setup()
    release = threading.Event()
    drawing = threading.Event()
    calls = []

    def slow_regenerate(only=None):
        calls.append(only)
        drawing.set()
        release.wait(5)
    server.regenerate = slow_regenerate
    live.redraw(["today"])
    assert drawing.wait(5)
    for _ in range(5):
        live.redraw(["today"])
    release.set()
    for _ in range(100):
        if not live._redrawing:
            break
        time.sleep(0.02)
    assert calls == ["today.png", "today.png"] and not live._redrawing


def test_the_first_save_turns_the_old_picture_block_into_photo_lists(setup):
    live, server, photo_pages, path, _ = setup(picture=("today", "hourly"))
    assert live.current()["today"]["photos"] == ["a1", "b2"]
    changed = live.save({"daily": {"photos": ["a1"]}})
    saved = yaml.safe_load(path.read_text())
    assert "picture" not in saved
    assert saved["pages"]["today"]["photos"] == ["a1", "b2"] and saved["pages"]["hourly"]["photos"] == ["a1", "b2"]
    assert "current" not in saved["pages"]
    assert changed == ["daily"]
    assert photo_pages == {"today": ["a1", "b2"], "hourly": ["a1", "b2"], "daily": ["a1"]}


@pytest.mark.parametrize("change, words", [
    ({"today": {"map": "relief"}}, "pages.today.map 'relief' does not exist"),
    ({"today": {"theme": "neon"}}, "pages.today.theme 'neon' does not exist"),
    ({"today": {"photos": "a1"}}, "pages.today.photos must be a list of photo ids"),
    ({"weekly": {"theme": "classic"}}, "weekly: no such page"),
    ({"today": "classic"}, "today: the settings must be a mapping"),
    ({"today": {"picture_size": 150}}, "themes.classic.today.picture_size must be a percent"),
    ({"today": {"picture_size": "big"}}, "themes.classic.today.picture_size must be a percent"),
])
def test_a_bad_change_is_refused_and_nothing_is_written(setup, change, words):
    live, server, photo_pages, path, _ = setup()
    with pytest.raises(ValueError, match=words):
        live.save(change)
    assert path.read_text() == _text() and server.redrawn == [] and photo_pages == {}


def test_a_read_only_config_is_refused(setup):
    live, server, _, path, _ = setup()
    os.chmod(path, 0o444)
    try:
        with pytest.raises(ValueError, match="config.yaml is read-only"):
            live.save({"today": {"photos": ["a1"]}})
    finally:
        os.chmod(path, 0o644)


def test_the_routes_read_and_save(setup):
    live, *_ = setup()
    app = Flask(__name__)
    app.register_blueprint(pages_blueprint(live))
    client = app.test_client()
    assert client.get("/pages/settings").get_json()["pages"]["today"] == {"theme": "classic", "photos": [], "map": "classic",
                                                                         "picture_size": None}
    rsp = client.post("/pages/settings", json={"current": {"photos": ["b2"]}})
    assert rsp.status_code == 200 and rsp.get_json()["changed"] == ["current"]
    assert rsp.get_json()["pages"]["current"]["photos"] == ["b2"]
    bad = client.post("/pages/settings", json={"today": {"map": "relief"}})
    assert bad.status_code == 400 and "does not exist" in bad.get_json()["problem"]
    assert client.post("/pages/settings", data="x", content_type="text/plain").status_code == 400
