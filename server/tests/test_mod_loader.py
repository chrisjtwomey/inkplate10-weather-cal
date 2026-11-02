"""Mods: real folders and real imports, with a fake renderer and no network."""
import logging
import logging.config
import os
import stat
import sys

import pytest
import yaml
from bs4 import BeautifulSoup
from epd_server.pipeline import regenerate
from epd_server.settings_page import settings_blueprint
from epd_server.source import StaticSource
from flask import Flask
from PIL import Image

import server
import settings_page as sp
import views.page
from mod_loader import ModError, load_mods

GEOMETRY = {"width": 200, "height": 300}

TIDES = '''
from airium import Airium
from epd_server.page import Page
from epd_server.settings_form import Field
from epd_server.source import DataSource

SETTINGS = (
    Field("apikey", "API key", "From your tides account.", "secret"),
    Field("station", "Station", "Such as Cobh.", default="Cobh"),
    Field("depth", "Depth", "", "int", 3, when="station=*"),
)

class Tides(DataSource):
    def __init__(self, apikey, station):
        self.apikey, self.station = apikey, station
    def datasets(self):
        return {"tides": lambda: f"{self.station} {self.apikey}"}

class TidesPage(Page):
    requires = ("tides", "map_url")
    def template(self, tides, map_url):
        self.airium = a = Airium()
        a("<!DOCTYPE html>")
        with a.html():
            with a.head():
                a.link(rel="stylesheet", href="tides.css")
            with a.body():
                a.p(_t=tides)

def setup(mod):
    return [TidesPage("tides", **mod.page_kwargs)], Tides(mod.get("apikey"), mod.get("station"))
'''


class FakeRenderer:
    def __init__(self, *a, **k):
        pass

    def render(self, html_path, width, height):
        return Image.new("RGB", (width, height), (180, 180, 180))


def write_mod(mods_dir, name, code, **files):
    folder = mods_dir / name
    folder.mkdir(parents=True)
    (folder / "mod.py").write_text(code)
    for filename, text in files.items():
        (folder / filename.replace("__", ".")).write_text(text)


def load(tmp_path, config=None, pages=(), sources=None):
    sources = [StaticSource(map_url="file:///map.png")] if sources is None else sources
    return load_mods(str(tmp_path / "mods"), str(tmp_path / "data" / "mods"), config or {}, GEOMETRY, list(pages), sources)


# ── Loading ──────────────────────────────────────────────────────────

def test_no_folder_means_no_mods(tmp_path):
    loaded = load(tmp_path)
    assert loaded.pages == [] and loaded.groups == ()
    assert set(loaded.source.datasets()) == {"map_url"}


def test_a_mods_page_renders_beside_its_own_files_and_gets_the_servers_data(tmp_path):
    write_mod(tmp_path / "mods", "tides", TIDES, tides__css="p {}")
    loaded = load(tmp_path, {"mods": {"tides": {"apikey": "k"}}})
    page = loaded.pages[0]
    page.renderer = FakeRenderer()
    assert [p.png_filename for p in regenerate(loaded.pages, loaded.source)] == ["tides.png"]

    out = tmp_path / "data" / "mods" / "tides"
    assert (out / "tides.png").exists() and (out / "tides.css").read_text() == "p {}"
    assert "Cobh k" in (out / "tides.html").read_text()
    assert not (out / "mod.py").exists()


def test_a_read_only_mod_can_be_copied_at_every_start_and_still_written_beside(tmp_path):
    write_mod(tmp_path / "mods", "tides", TIDES, tides__css="p {}")
    folder = tmp_path / "mods" / "tides"
    os.chmod(folder / "tides.css", stat.S_IREAD)
    os.chmod(folder, stat.S_IREAD | stat.S_IEXEC)
    try:
        load(tmp_path)
        loaded = load(tmp_path)
        loaded.pages[0].renderer = FakeRenderer()
        regenerate(loaded.pages, loaded.source)
    finally:
        os.chmod(folder, stat.S_IRWXU)
    out = tmp_path / "data" / "mods" / "tides"
    assert (out / "tides.css").read_text() == "p {}" and (out / "tides.png").exists()


def test_a_page_keeps_its_image_across_a_start(tmp_path):
    write_mod(tmp_path / "mods", "tides", TIDES)
    load(tmp_path)
    image = tmp_path / "data" / "mods" / "tides" / "tides.png"
    image.write_text("old")
    load(tmp_path)
    assert image.read_text() == "old"


def test_mods_load_in_name_order_and_may_add_no_source(tmp_path):
    code = '''
from epd_server.page import Page
class P(Page):
    requires = ("map_url",)
def setup(mod):
    return [P(mod.name, **mod.page_kwargs)], None
'''
    write_mod(tmp_path / "mods", "zebra", code)
    write_mod(tmp_path / "mods", "apple", code)
    (tmp_path / "mods" / "__pycache__").mkdir()
    (tmp_path / "mods" / "notes.txt").write_text("not a mod")
    assert [p.name for p in load(tmp_path).pages] == ["apple", "zebra"]


# ── Settings values ──────────────────────────────────────────────────

SETTING = '''
from epd_server.settings_form import Field
SETTINGS = (Field("station", "Station", default="Cobh"), Field("depth", "Depth", "", "int", 3))
seen = {}
def setup(mod):
    seen.update(station=mod.get("station"), depth=mod.get("depth"), apikey=mod.get("apikey"))
    return [], None
'''


def seen_settings(tmp_path, config):
    write_mod(tmp_path / "mods", "tides", SETTING)
    load(tmp_path, config)
    return sys.modules["weather_cal_mod_tides"].seen


def test_a_setting_absent_from_the_file_has_its_fields_default_or_none(tmp_path):
    assert seen_settings(tmp_path, {}) == {"station": "Cobh", "depth": 3, "apikey": None}


def test_a_setting_comes_from_the_file_and_a_blank_one_is_none(tmp_path):
    config = {"mods": {"tides": {"station": "Galway", "apikey": ""}}}
    assert seen_settings(tmp_path, config) == {"station": "Galway", "depth": 3, "apikey": None}


def test_an_environment_variable_overrides_the_file_with_the_fields_type(tmp_path, monkeypatch):
    monkeypatch.setenv("MODS_TIDES_APIKEY", "from-env")
    monkeypatch.setenv("MODS_TIDES_DEPTH", "7")
    config = {"mods": {"tides": {"apikey": "from-file"}}}
    assert seen_settings(tmp_path, config) == {"station": "Cobh", "depth": 7, "apikey": "from-env"}


def test_a_mod_with_no_key_yet_still_loads(tmp_path):
    write_mod(tmp_path / "mods", "tides", TIDES)
    assert [p.name for p in load(tmp_path).pages] == ["tides"]


# ── A mod that cannot load ───────────────────────────────────────────

PAGE_NAMED = '''
from epd_server.page import Page
class P(Page):
    requires = ()
def setup(mod):
    return [P("today", **mod.page_kwargs)], None
'''

@pytest.mark.parametrize("code, says", [
    ("this is not python", "failed to load"),
    ("raise RuntimeError('import fault')", "import fault"),
    ("X = 1", "setup"),
    ("def setup(mod):\n    raise RuntimeError('setup fault')", "setup fault"),
    ("def setup(mod):\n    return None", "failed to load"),
])
def test_a_fault_in_a_mods_code_names_the_mod(tmp_path, code, says):
    write_mod(tmp_path / "mods", "tides", code)
    with pytest.raises(ModError, match="Mod tides") as caught:
        load(tmp_path)
    assert says in str(caught.value)


def test_a_folder_with_no_mod_file_is_refused(tmp_path):
    (tmp_path / "mods" / "tides").mkdir(parents=True)
    with pytest.raises(ModError, match="Mod tides: the folder has no mod.py"):
        load(tmp_path)


@pytest.mark.parametrize("name", ["Tides", "my-tides", "a.b"])
def test_a_folder_name_that_cannot_be_a_key_is_refused(tmp_path, name):
    write_mod(tmp_path / "mods", name, TIDES)
    with pytest.raises(ModError, match="rename the folder"):
        load(tmp_path)


def test_a_page_name_already_in_use_is_refused(tmp_path):
    write_mod(tmp_path / "mods", "taken", PAGE_NAMED)
    existing = views.page.Page("today", 200, 300)
    with pytest.raises(ModError, match="Mod taken: another page is already named today"):
        load(tmp_path, pages=[existing])


def test_a_data_name_two_sources_give_is_refused(tmp_path):
    code = '''
from epd_server.source import StaticSource
def setup(mod):
    return [], StaticSource(map_url="mine")
'''
    write_mod(tmp_path / "mods", "clash", code)
    with pytest.raises(ModError, match="Mod clash: dataset 'map_url'"):
        load(tmp_path)


def test_a_page_that_requires_data_no_source_gives_is_refused(tmp_path):
    code = '''
from epd_server.page import Page
class P(Page):
    requires = ("nothing_gives_this",)
def setup(mod):
    return [P("p", **mod.page_kwargs)], None
'''
    write_mod(tmp_path / "mods", "lost", code)
    with pytest.raises(ModError, match="Mod lost: no source gives nothing_gives_this"):
        load(tmp_path)


def test_a_page_made_without_the_page_arguments_is_refused(tmp_path):
    code = '''
from epd_server.page import Page
class P(Page):
    requires = ()
def setup(mod):
    return [P("p", 200, 300)], None
'''
    write_mod(tmp_path / "mods", "lost", code)
    with pytest.raises(ModError, match="Mod lost failed to load"):
        load(tmp_path)


# ── Settings page ────────────────────────────────────────────────────

def site(tmp_path, groups, text=""):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    app = Flask(__name__)
    app.register_blueprint(settings_blueprint(sp.form_with_mods(groups), str(path), lambda t: None, restart=lambda: None))
    return app.test_client(), path


def test_a_mod_with_no_settings_adds_no_tab(tmp_path):
    write_mod(tmp_path / "mods", "plain", "def setup(mod):\n    return [], None\n")
    loaded = load(tmp_path)
    assert loaded.groups == ()
    assert sp.form_with_mods(loaded.groups) is sp.FORM


def test_each_mod_with_settings_is_a_section_of_one_tab_under_its_own_keys(tmp_path):
    write_mod(tmp_path / "mods", "tides", TIDES)
    write_mod(tmp_path / "mods", "bin_days", SETTING)
    groups = load(tmp_path).groups
    assert [g.heading for g in groups] == ["Bin days", "Tides"]

    form = sp.form_with_mods(groups)
    assert form.tabs[-1].name == "mods" and form.tabs[-1].title == "Mods"
    assert form.by_key["mods.tides.apikey"].kind == "secret"
    assert form.by_key["mods.tides.depth"].when == "mods.tides.station=*"


def test_a_save_writes_a_mods_setting_and_its_secret_never_reaches_the_page(tmp_path):
    write_mod(tmp_path / "mods", "tides", TIDES)
    client, path = site(tmp_path, load(tmp_path).groups, "mods:\n  tides:\n    apikey: SECRET\n")

    page = client.get("/settings").data.decode()
    assert "Tides" in page and "From your tides account." in page
    assert "SECRET" not in page

    rsp = client.post("/settings", data={"mode": "form", "action": "save", "mods.tides.station": "Galway",
                                         "mods.tides.apikey": ""})
    assert rsp.status_code < 400
    saved = yaml.safe_load(path.read_text())
    assert saved["mods"]["tides"] == {"apikey": "SECRET", "station": "Galway"}


def test_a_key_an_environment_variable_sets_is_locked(tmp_path, monkeypatch):
    monkeypatch.setenv("MODS_TIDES_STATION", "Kinsale")
    write_mod(tmp_path / "mods", "tides", TIDES)
    client, _ = site(tmp_path, load(tmp_path).groups)
    control = BeautifulSoup(client.get("/settings").data, "html.parser").find(attrs={"name": "mods.tides.station"})
    assert control.has_attr("disabled")


# ── The server ───────────────────────────────────────────────────────

class StubGoogle:
    def __init__(self, *a, **k):
        pass

    def get_static_map_local_src(self, map_id, location):
        return "map.png"


@pytest.fixture
def project(tmp_path, monkeypatch):
    config = {
        "server": {"port": 8080, "timezone": "Europe/Dublin"},
        "display": {"pools": {"a": ["today.png"], "b": ["tides.png"]},
                    "schedule": {"type": "times", "08:00:00": "a", "20:00:00": "b"}},
        "weather": {"service": "mock"},
        "google": {"apikey": "G", "staticmaps_mapid": "M"},
        "location": "Dublin",
        "image": {"width": 200, "height": 300},
        "mods": {"tides": {"apikey": "k"}},
    }
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setattr(server, "cwd", str(tmp_path))
    monkeypatch.setattr(server, "GoogleAPIService", StubGoogle)
    monkeypatch.setattr(logging.config, "fileConfig", lambda *a, **k: None)
    monkeypatch.setattr("epd_server.page.ChromiumRenderer", FakeRenderer)
    monkeypatch.setattr(views.page, "HTML_DIR", str(tmp_path / "html"))
    monkeypatch.setattr(views.page, "PNG_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(sys, "argv", ["server.py", "--once"])
    return tmp_path


def test_the_server_renders_and_schedules_a_mods_page(project):
    write_mod(project / "mods", "tides", TIDES)
    server.main()
    assert (project / "data" / "mods" / "tides" / "tides.png").exists()
    assert (project / "out" / "today.png").exists()


def test_the_settings_check_knows_a_mods_page(project, monkeypatch):
    made = {}

    class FakeServer:
        def __init__(self, **kwargs):
            self.app = Flask(__name__)
            self.network = kwargs["network"]
            made["server"] = self

        def run(self, once=False):
            pass

    write_mod(project / "mods", "tides", TIDES)
    monkeypatch.delenv("WEATHER_CAL_PASSWORD", raising=False)
    monkeypatch.setattr(server, "DisplayServer", FakeServer)
    server.main()

    rsp = made["server"].app.test_client().post("/settings", data={
        "mode": "form", "action": "save", "display.pools": "1", "display.pools.name": ["a"],
        "display.pools.pages": ["nosuchpage.png"], "display.schedule": "1",
        "display.schedule.at": ["08:00"], "display.schedule.pool": ["a"]})
    words = BeautifulSoup(rsp.data, "html.parser").get_text()
    assert rsp.status_code == 400
    assert "does not exist: nosuchpage.png" in words and "tides.png" in words


def test_a_mod_that_cannot_load_stops_the_server_with_its_name_in_the_log(project, caplog):
    write_mod(project / "mods", "tides", "raise RuntimeError('import fault')")
    with pytest.raises(SystemExit) as stopped:
        server.main()
    assert stopped.value.code == 1
    assert "Mod tides failed to load" in caplog.text
