"""The Settings page: what it shows, what a save writes, and the sign-in in front of it."""
import os
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from epd_server.config import parse_network
from epd_server.login import Login, guard
from flask import Flask

import settings_page as sp

CONFIG = """\
# The server's own settings.
server:
  port: 8080  # the panel fetches from here
display:
  pools:
    today: [today.png]
  schedule:
    type: times
    "08:00:00": today
client:
  # What a USB flash writes.
  server_url: http://old.local:8080
  wifi:
    ssid: old-wifi
    password: old-password
  firmware:
    enabled: false
"""
PASSWORD = "correct horse"


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(CONFIG)
    return p


def site(path, login, mqtt_on=False):
    import yaml
    app = Flask(__name__)
    server = SimpleNamespace(network=parse_network(yaml.safe_load(path.read_text())))
    app.register_blueprint(sp.settings_blueprint(str(path), server, login, mqtt_on))
    app.server = server

    @app.route("/today.png")
    def page():
        return "png"

    return app


@pytest.fixture
def no_login(tmp_path):
    return Login("", str(tmp_path / "login.json"))


@pytest.fixture
def client(path, no_login):
    return site(path, no_login).test_client()


def form(**over):
    return {"server_url": "http://old.local:8080", "ssid": "old-wifi", "password": "", **over}


def soup(rsp):
    return BeautifulSoup(rsp.data, "html.parser")


# ── What the page shows ──────────────────────────────────────────────

def test_the_page_shows_the_values_but_never_the_password(client):
    rsp = client.get("/settings")
    page = soup(rsp)
    assert page.find(id="server_url")["value"] == "http://old.local:8080"
    assert page.find(id="ssid")["value"] == "old-wifi"
    assert page.find(id="password")["value"] == ""
    assert page.find(id="password")["placeholder"] == "Leave blank to keep it"
    assert b"old-password" not in rsp.data
    assert rsp.headers["Cache-Control"] == "no-store"


def test_the_mqtt_field_shows_only_with_mqtt_on(path, no_login):
    assert soup(site(path, no_login).test_client().get("/settings")).find(id="mqtt_host") is None
    assert soup(site(path, no_login, mqtt_on=True).test_client().get("/settings")).find(id="mqtt_host")


def test_with_no_password_the_page_says_anyone_can_change_it(client):
    page = soup(client.get("/settings"))
    assert page.find(id="no-password").text == sp.NO_PASSWORD
    assert page.find(id="access-token") is None


def test_a_read_only_file_is_named_before_a_save(path, no_login):
    path.chmod(0o444)
    try:
        page = soup(site(path, no_login).test_client().get("/settings"))
        if os.access(path, os.W_OK):
            pytest.skip("running as root")
        assert page.find(id="read-only").text == sp.READ_ONLY
    finally:
        path.chmod(0o644)


# ── A save ───────────────────────────────────────────────────────────

def test_a_save_changes_only_its_lines_and_keeps_the_comments(path, client):
    rsp = client.post("/settings", data=form(ssid="new-wifi"))
    assert (rsp.status_code, rsp.headers["Location"]) == (303, "settings?saved=1")
    assert path.read_text() == CONFIG.replace("ssid: old-wifi", "ssid: new-wifi")
    assert (path.parent / "config.yaml.bak").read_text() == CONFIG
    assert soup(client.get(rsp.headers["Location"])).find(id="notice").text == "Settings saved."


def test_a_save_takes_effect_without_a_restart(path, no_login):
    app = site(path, no_login)
    app.test_client().post("/settings", data=form(ssid="new-wifi", password="a-new-password"))
    assert app.server.network.wifi_ssid == "new-wifi"
    assert app.server.network.wifi_password == "a-new-password"


def test_a_blank_password_keeps_the_one_in_the_file(path, client):
    client.post("/settings", data=form(password=""))
    assert "password: old-password" in path.read_text()


@pytest.mark.parametrize("password", ["has # a: hash", "12345678", "'quoted'", 'dou"ble"', "yes-true"])
def test_a_password_comes_back_as_it_was_typed(path, no_login, password):
    app = site(path, no_login)
    app.test_client().post("/settings", data=form(password=password))
    assert app.server.network.wifi_password == password
    import yaml
    assert yaml.safe_load(path.read_text())["client"]["wifi"]["password"] == password


def test_a_file_with_no_client_block_gets_one(path, no_login):
    path.write_text("# Only a comment.\nserver:\n  port: 8080\n")
    site(path, no_login).test_client().post(
        "/settings", data={"server_url": "http://new.local:8080", "ssid": "w", "password": "12345678"})
    text = path.read_text()
    assert text.startswith("# Only a comment.\n") and "ssid: w" in text


# ── A refused save ───────────────────────────────────────────────────

@pytest.mark.parametrize("field, value, words", [
    ("server_url", "http://new.local:8080/path", sp.SERVER_URL.refused),
    ("server_url", "not an address", sp.SERVER_URL.refused),
    ("ssid", "x" * 33, sp.WIFI_NAME.refused),
    ("password", "short", sp.WIFI_PASSWORD.refused),
])
def test_a_bad_value_is_refused_and_the_file_stays(path, client, field, value, words):
    rsp = client.post("/settings", data=form(**{field: value}))
    assert rsp.status_code == 400
    assert soup(rsp).find(id=f"{field}-problem").text == words
    assert path.read_text() == CONFIG
    assert not (path.parent / "config.yaml.bak").exists()


def test_a_refused_save_keeps_what_was_typed_but_not_the_password(client):
    rsp = client.post("/settings", data=form(ssid="typed", server_url="bad", password="typed-password"))
    page = soup(rsp)
    assert page.find(id="ssid")["value"] == "typed"
    assert page.find(id="password")["value"] == ""
    assert b"typed-password" not in rsp.data


def test_a_broker_address_with_a_port_is_refused(path, no_login):
    client = site(path, no_login, mqtt_on=True).test_client()
    rsp = client.post("/settings", data=form(mqtt_host="broker:1883"))
    assert soup(rsp).find(id="mqtt_host-problem").text == sp.MQTT_HOST.refused


def test_a_file_it_cannot_write_says_so_and_nothing_changes(path, client, monkeypatch):
    def refused(*_):
        raise PermissionError("read-only")
    monkeypatch.setattr(sp, "save", refused)
    rsp = client.post("/settings", data=form(ssid="new-wifi"))
    assert rsp.status_code == 500
    assert soup(rsp).find(id="problem").text == sp.READ_ONLY
    assert path.read_text() == CONFIG


# ── Behind the sign-in ───────────────────────────────────────────────

@pytest.fixture
def login(tmp_path):
    return Login(PASSWORD, str(tmp_path / "login.json"))


@pytest.fixture
def guarded(path, login):
    app = site(path, login)
    guard(app, login, sp.SITE)
    return app.test_client()


def sign_in(client):
    return client.post("/login", data={"password": PASSWORD, "next": "/settings"})


def test_the_page_asks_a_browser_to_sign_in(guarded):
    rsp = guarded.get("/settings", headers={"Accept": "text/html"})
    assert (rsp.status_code, rsp.headers["Location"]) == (303, "/login?next=/settings")


def test_a_save_needs_a_sign_in(path, guarded):
    assert guarded.post("/settings", data=form(ssid="new")).status_code == 401
    assert path.read_text() == CONFIG


def test_a_save_from_another_site_is_refused(path, guarded):
    sign_in(guarded)
    rsp = guarded.post("/settings", data=form(ssid="new"), headers={"Origin": "http://evil.example"})
    assert rsp.status_code == 403 and path.read_text() == CONFIG


def test_a_board_still_reaches_its_page(guarded):
    assert guarded.get("/today.png").data == b"png"


def test_a_signed_in_person_sees_the_token_and_can_replace_it(guarded, login):
    sign_in(guarded)
    page = soup(guarded.get("/settings"))
    assert page.find(id="access-token")["value"] == login.token
    assert page.find(id="no-password") is None
    old = login.token
    rsp = guarded.post("/settings/token")
    assert (rsp.status_code, rsp.headers["Location"]) == (303, "../settings")
    assert login.token != old


def test_sign_out_ends_it(guarded):
    sign_in(guarded)
    assert guarded.post("/logout").status_code == 303
    assert guarded.get("/settings").status_code == 401
