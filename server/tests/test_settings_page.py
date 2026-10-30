"""This server's settings on epd's page: every key in config.yaml, the sign-in, and a real check."""
import os

import pytest
import yaml
from bs4 import BeautifulSoup
from epd_server.config_file import flat, read
from epd_server.login import Login, guard
from epd_server.settings_page import settings_blueprint
from flask import Flask

import settings_page as sp
from server import load_settings

EXAMPLE = open(os.path.join(os.path.dirname(__file__), "..", "config.example.yaml")).read()
PASSWORD = "correct horse"


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(EXAMPLE)
    return p


def site(path, login=None):
    """The page on ``path``, with a real check, and restarts counted."""
    app = Flask(__name__)
    app.restarts = 0

    def restart():
        app.restarts += 1

    app.register_blueprint(settings_blueprint(sp.FORM, str(path), lambda t: sp.check_config(t, load_settings),
                                              restart=restart, login=login))
    if login is not None:
        guard(app, login, sp.SITE)

    @app.route("/today.png")
    def page():
        return "png"

    return app


def soup(rsp):
    return BeautifulSoup(rsp.data, "html.parser")


def post(client, action="save", **fields):
    data = {k.replace("__", "."): v for k, v in fields.items()}
    return client.post("/settings", data={"mode": "form", "action": action, **data})


# ── Every option ─────────────────────────────────────────────────────

def test_every_key_in_the_example_has_a_field():
    paths = {f.path for f in sp.FORM.fields}
    missing = [".".join(p) for p in flat(yaml.safe_load(EXAMPLE))
               if not any(p[:len(f)] == f for f in paths)]
    assert missing == []


def test_every_provider_is_a_choice():
    from weather.registry import registered_services
    assert {c for c, _ in sp.FORM.by_key["weather.service"].choices} == set(registered_services())


def test_the_defaults_are_the_ones_the_server_uses():
    config = {"weather": {"service": "mock"}, "google": {"apikey": "G", "staticmaps_mapid": "M"}, "location": "Cork"}
    cfg = load_settings(config)
    d = sp.FORM.defaults(config)
    assert d["server.port"] == str(cfg.core.server.port)
    assert d["server.https_port"] == str(cfg.core.server.https_port)
    assert d["server.regen_lead_seconds"] == str(cfg.core.server.regen_lead_seconds)
    assert d["image.width"] == str(cfg.core.image.width) and d["image.height"] == str(cfg.core.image.height)
    assert d["image.innerWidth"] == str(cfg.core.image.inner_width)
    assert d["image.innerAlignX"] == cfg.core.image.inner_align_x
    assert d["client.firmware.enabled"] == ("true" if cfg.core.firmware.enabled else "false")
    assert d["mqtt.host"] == cfg.core.mqtt.host and d["mqtt.port"] == str(cfg.core.mqtt.port)
    assert d["mqtt.prefix"] == cfg.core.mqtt.prefix
    assert d["logs.path"] == cfg.logs_path and float(d["logs.keep_days"]) == cfg.logs_days
    assert d["weather.num_hourly_forecasts"] == str(cfg.num_hourly_forecasts)
    assert d["weather.metric"] == "true"


def test_the_page_never_shows_a_key_or_a_password(path):
    path.write_text(EXAMPLE.replace("apikey: XXXX", "apikey: VERY-SECRET") + "\n")
    rsp = site(path).test_client().get("/settings")
    assert b"VERY-SECRET" not in rsp.data


def test_each_page_shows_the_schedule_as_rows(path):
    page = soup(site(path).test_client().get("/settings"))
    table = page.find("table", attrs={"data-key": "display.schedule"})
    first = table.select_one("tbody tr").select("input")
    assert [i["value"] for i in first] == ["08:00:00", "today"]


# ── A save, with the real check ──────────────────────────────────────

def test_a_save_keeps_the_examples_comments_and_changes_only_its_line(path):
    client = site(path).test_client()
    assert post(client, location="Galway").status_code == 200
    assert path.read_text() == EXAMPLE.replace("location: Dublin", "location: Galway")


def test_the_server_check_refuses_what_would_stop_a_start(path):
    client = site(path).test_client()
    rsp = post(client, server__port="8443")
    assert rsp.status_code == 400 and path.read_text() == EXAMPLE
    assert soup(rsp).find(id="f-server-https_port-problem").text == "Port and HTTPS port cannot be the same."


def test_a_set_the_wake_times_do_not_name_is_refused(path):
    client = site(path).test_client()
    rsp = client.post("/settings", data={"mode": "form", "action": "save", "display.schedule": "1",
                                         "display.schedule.at": ["08:00"], "display.schedule.pool": ["nope"]})
    assert rsp.status_code == 400 and path.read_text() == EXAMPLE


def test_a_bad_wifi_password_says_what_to_enter(path):
    rsp = post(site(path).test_client(), client__wifi__password="short")
    assert soup(rsp).find(id="f-client-wifi-password-problem").text == "Enter 8 to 63 characters."


@pytest.mark.parametrize("password", ["has # a: hash", "12345678", "'quoted'", 'dou"ble"'])
def test_a_wifi_password_reads_back_as_typed(path, password):
    post(site(path).test_client(), client__wifi__password=password)
    assert read(path.read_text())["client"]["wifi"]["password"] == password


def test_the_saved_file_starts_the_server(path):
    post(site(path).test_client(), location="Galway", server__port="9090", mqtt__enabled="true")
    cfg = load_settings(yaml.safe_load(path.read_text()))
    assert cfg.location == "Galway" and cfg.core.server.port == 9090 and cfg.core.mqtt.enabled


def test_restart_runs_after_a_save(path):
    app = site(path)
    post(app.test_client(), location="Galway")
    assert app.restarts == 1


# ── Behind the sign-in ───────────────────────────────────────────────

@pytest.fixture
def login(tmp_path):
    return Login(PASSWORD, str(tmp_path / "login.json"))


def test_the_page_asks_a_browser_to_sign_in(path, login):
    rsp = site(path, login).test_client().get("/settings", headers={"Accept": "text/html"})
    assert (rsp.status_code, rsp.headers["Location"]) == (303, "/login?next=/settings")


def test_a_save_needs_a_sign_in_and_another_site_is_refused(path, login):
    client = site(path, login).test_client()
    assert post(client, location="Galway").status_code == 401
    client.post("/login", data={"password": PASSWORD})
    rsp = client.post("/settings", data={"mode": "form", "action": "save", "location": "Galway"},
                      headers={"Origin": "http://evil.example"})
    assert rsp.status_code == 403 and path.read_text() == EXAMPLE


def test_a_board_still_reaches_its_page(path, login):
    assert site(path, login).test_client().get("/today.png").data == b"png"
