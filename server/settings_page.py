"""The sign-in, and GET and POST /settings: the network settings a USB flash
writes to a board, saved to config.yaml.

Every other setting stays in config.yaml, which a person edits for the API keys
anyway. A save takes effect at once, since only an install reads these.
"""
from __future__ import annotations

import html
import io
import os
import shutil
from dataclasses import dataclass

from epd_server.config import ConfigError, load_yaml, parse_network
from epd_server.login import Login, SignInSite
from flask import Blueprint, make_response, redirect, request
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError as RuamelYAMLError
from yaml import YAMLError

PASSWORD_ENV = "WEATHER_CAL_PASSWORD"
SITE = SignInSite("weather-cal", data=frozenset({"/network.bin", "/logs"}), home="/settings")

READ_ONLY = "Cannot save: config.yaml is read-only. Mount it writable, then restart the server."
NOT_YAML = "Cannot save: config.yaml has a mistake in it. Correct the file, then save again."
NO_PASSWORD = (f"No password is set, so anyone on the network can change these settings. "
               f"Set {PASSWORD_ENV} to turn on sign-in.")


@dataclass(frozen=True)
class Field:
    name: str          # the form's field
    keys: tuple[str, ...]   # where it sits in config.yaml
    label: str
    help: str
    refused: str       # what a value parse_network refuses gets told


SERVER_URL = Field("server_url", ("client", "server_url"), "Server address",
                   "Boards get this address when installing firmware.",
                   "Enter it as http://host:port, with nothing after the port.")
WIFI_NAME = Field("ssid", ("client", "wifi", "ssid"), "Wi-Fi name", "",
                  "Too long. A Wi-Fi name has at most 32 characters.")
WIFI_PASSWORD = Field("password", ("client", "wifi", "password"), "Wi-Fi password",
                      "8 to 63 characters.", "Enter 8 to 63 characters.")
MQTT_HOST = Field("mqtt_host", ("client", "mqtt_host"), "MQTT broker",
                  "The address boards reach the broker at.",
                  "Enter the name or address alone. The port is in config.yaml.")


def _with_key(config: dict, keys: tuple[str, ...], value: str) -> dict:
    """A copy of ``config`` with ``value`` at ``keys``, and nothing else changed."""
    changed = dict(config)
    level = changed
    for key in keys[:-1]:
        level[key] = dict(level.get(key) or {})
        level = level[key]
    level[keys[-1]] = value
    return changed


def refusals(fields: list[Field], config: dict, form) -> dict[str, str]:
    """What is wrong with each field the form sent, by field name."""
    wrong = {}
    for f in fields:
        given = form.get(f.name, "").strip()
        if not given:
            continue
        try:
            parse_network(_with_key(config, f.keys, given))
        except ConfigError:
            wrong[f.name] = f.refused
    return wrong


def edited(text: str, values: list[tuple[tuple[str, ...], str]]) -> str:
    """``text``, a YAML file, with each value at its keys, keeping its comments."""
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    y.explicit_start = text.startswith("---")
    data = y.load(text) or {}
    for keys, value in values:
        level = data
        for key in keys[:-1]:
            if level.get(key) is None:
                level[key] = {}
            level = level[key]
        level[keys[-1]] = value
    out = io.StringIO()
    y.dump(data, out)
    return out.getvalue()


def save(path: str, text: str) -> None:
    """Keep ``path`` as it was beside it, then write ``text`` over it in place:
    a file mounted into a container on its own cannot be replaced by a rename."""
    shutil.copy(path, path + ".bak")
    with open(path, "w") as f:
        f.write(text)


def _field_html(f: Field, value: str, problem: str, password_set: bool) -> str:
    is_password = f is WIFI_PASSWORD
    kind = "password" if is_password else "text"
    attrs = 'autocomplete="new-password"' if is_password else 'autocomplete="off"'
    if is_password and password_set:
        attrs += ' placeholder="Leave blank to keep it"'
    help_text = f'<p class="help">{html.escape(f.help)}</p>' if f.help else ""
    alert = f'<p class="problem" id="{f.name}-problem" role="alert">{html.escape(problem)}</p>' \
        if problem else ""
    return (f'<div class="field"><label for="{f.name}">{html.escape(f.label)}</label>'
            f'<input type="{kind}" id="{f.name}" name="{f.name}" {attrs} '
            f'value="{html.escape(value, quote=True)}">{help_text}{alert}</div>')


def settings_html(fields: list[Field], values: dict[str, str], problems: dict[str, str],
                  *, notice: str = "", alert: str = "", login: Login, writable: bool,
                  password_set: bool) -> str:
    """The page. ``values`` hold every field but the password, which a page never shows."""
    rows = "".join(_field_html(f, values.get(f.name, ""), problems.get(f.name, ""), password_set)
                   for f in fields)
    banners = "".join(f'<p class="banner problem" id="{i}" role="alert">{html.escape(t)}</p>'
                      for i, t in (("problem", alert),
                                   ("read-only", "" if writable else READ_ONLY),
                                   ("no-password", "" if login.on else NO_PASSWORD)) if t)
    if notice:
        banners += f'<p class="banner" id="notice" role="status">{html.escape(notice)}</p>'
    access = ""
    if login.on:
        access = (
            '<h2>Access token</h2>'
            '<p class="help">Other apps send this to read the logs, and to install from a terminal.</p>'
            f'<input type="text" id="access-token" readonly value="{html.escape(login.token, quote=True)}">'
            '<form method="post" action="settings/token">'
            '<button type="submit">Replace token</button></form>'
            '<form method="post" action="logout"><button type="submit">Sign out</button></form>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Settings</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto; padding: 0 1rem; }}
label {{ display: block; font-weight: 600; margin-top: 1rem; }}
input {{ display: block; width: 100%; box-sizing: border-box; font: inherit; padding: .5rem; margin-top: .25rem; }}
button {{ font: inherit; padding: .5rem 1rem; margin-top: 1rem; }}
.help {{ color: #555; margin: .25rem 0 0; font-size: .9rem; }}
.problem {{ color: #b00020; margin: .25rem 0 0; }}
.banner {{ padding: .5rem .75rem; border: 1px solid currentColor; border-radius: 4px; }}
@media (prefers-color-scheme: dark) {{
  .help {{ color: #aaa; }}
  .problem {{ color: #ff8a80; }}
}}
</style>
</head>
<body>
<h1>Settings</h1>
<p>Boards get these when you <a href="install">install firmware</a>. Every other setting is in config.yaml.</p>
{banners}
<form method="post" action="settings" id="settings-form" novalidate>
{rows}
<button type="submit">Save changes</button>
</form>
{access}
</body>
</html>
"""


def _page(page: str, status: int = 200):
    rsp = make_response(page, status)
    rsp.headers["Cache-Control"] = "no-store"
    return rsp


def settings_blueprint(path: str, server, login: Login, mqtt_on: bool) -> Blueprint:
    """The page for the config file at ``path``. A save gives ``server`` the new
    network settings, which its install routes read at each request."""
    bp = Blueprint("settings", __name__)
    fields = [SERVER_URL, WIFI_NAME, WIFI_PASSWORD] + ([MQTT_HOST] if mqtt_on else [])

    def current() -> dict[str, str]:
        n = server.network
        return {"server_url": n.server_url, "ssid": n.wifi_ssid, "mqtt_host": n.mqtt_host}

    def show(values: dict[str, str], problems: dict[str, str], status: int = 200,
             notice: str = "", alert: str = ""):
        return _page(settings_html(fields, values, problems, notice=notice, alert=alert,
                                   login=login, writable=os.access(path, os.W_OK),
                                   password_set=bool(server.network.wifi_password)), status)

    @bp.route("/settings", methods=["GET"])
    def view():
        saved = "Settings saved." if request.args.get("saved") else ""
        return show(current(), {}, notice=saved)

    @bp.route("/settings", methods=["POST"])
    def change():
        typed = {f.name: request.form.get(f.name, "").strip()
                 for f in fields if f is not WIFI_PASSWORD}
        try:
            config = load_yaml(path)
        except (YAMLError, ConfigError):
            return show(typed, {}, 500, alert=NOT_YAML)
        problems = refusals(fields, config, request.form)
        if problems:
            return show(typed, problems, 400)
        # A blank password keeps the one in the file; every other blank clears its key.
        values = [(f.keys, request.form.get(f.name, "").strip()) for f in fields
                  if f is not WIFI_PASSWORD or request.form.get(f.name, "").strip()]
        try:
            with open(path) as f:
                text = edited(f.read(), values)
            save(path, text)
            server.network = parse_network(load_yaml(path))
        except OSError:
            return show(typed, {}, 500, alert=READ_ONLY)
        except RuamelYAMLError:
            return show(typed, {}, 500, alert=NOT_YAML)
        return redirect("settings?saved=1", 303)

    @bp.route("/settings/token", methods=["POST"])
    def replace_token():
        if login.on:
            login.replace_token()
        return redirect("../settings", 303)

    return bp
