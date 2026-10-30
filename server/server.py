#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inkplate weather calendar server.

Everything generic — HTTP routes, the X-Next-* headers, the regeneration
loop, the client log relay, signal handling — is epd_server.DisplayServer.
This file is the project: its config keys, its weather service, its five
pages, and one run() call.
"""

import os
import socket
import sys
import json
import argparse
import dataclasses
import logging.config
from typing import NoReturn

from utils import get_prop, get_prop_by_keys
from views.hourly import HourlyPage
from views.today import TodayPage
from views.current import CurrentPage
from views.daily import DailyPage
from views.tomorrow import TomorrowPage
from google.api import GoogleAPIService, StaticMapSource
from epd_server import DisplayServer, InstallBoard, LogsQuery, LogStore, align_process_timezone
from epd_server.config import ConfigError, CoreConfig, load_core_config, load_yaml
from epd_server.login import Login, guard
from epd_server.source import CompositeSource
from settings_page import PASSWORD_ENV, SITE, settings_blueprint

cwd = os.path.dirname(os.path.realpath(__file__))
log = logging.getLogger("server")

# One wake a day when config.yaml has no display block.
DEFAULT_DISPLAY = {"pools": {"today": ["today.png"]},
                   "schedule": {"type": "times", "09:00:00": "today"}}

FIRMWARE_PRODUCT = "inkplate10-weather-cal"
# The Inkplate 10's USB-to-serial chip is a CH340C.
INSTALL_BOARDS = [InstallBoard(FIRMWARE_PRODUCT, "Display", chip="ESP32", usb_vendor_ids=(0x1A86,))]


# Import all service modules so that their @register decorators run and
# populate the registry before validate_config() uses it.
import weather.accuweather.accuweather  # noqa: F401
import weather.openweathermap.openweathermap  # noqa: F401
import weather.mock.mock  # noqa: F401
import weather.meteireann.meteireann  # noqa: F401
import weather.openmeteo.openmeteo  # noqa: F401
from weather.registry import create as _create_weather_service, needs_apikey, registered_services
from weather.service import DeferredWeather


def _server_version() -> str:
    try:
        with open(os.path.join(cwd, "version.json")) as f:
            version_info = json.load(f)
    except Exception:
        return "dev"

    version = str(version_info.get("version") or "dev")
    commit_sha = str(version_info.get("commitSha") or "").strip()
    if commit_sha:
        return f"{version}+{commit_sha}"
    return version


@dataclasses.dataclass(frozen=True)
class ServerConfig:
    """epd's config, and the keys only this project has."""
    core: CoreConfig
    weather_service: str      # one of registered_services()
    weather_apikey: str | None  # None for a provider with no key
    weather_metric: bool
    num_hourly_forecasts: int
    google_apikey: str
    staticmaps_mapid: str
    location: str
    logs_path: str            # the boards' log lines, relative to this folder
    logs_days: float          # how long a line is kept


def validate_config(config: dict) -> ServerConfig:
    """Parse the raw config dict, apply defaults, and validate all values.

    The generic blocks (server, image, mqtt, display, debug) are
    validated by epd_server.config.load_core_config. This function adds the
    keys only this project has (weather, google, location), then flattens
    everything into ServerConfig for main().

    Logs a clear error and exits immediately on any invalid value rather than
    letting a bad entry surface as an obscure exception later at runtime.
    """
    def _err(msg: str) -> NoReturn:
        log.error(msg)
        sys.exit(1)

    try:
        core = load_core_config(
            config,
            default_display=DEFAULT_DISPLAY,
            default_firmware_product=FIRMWARE_PRODUCT,
            base_dir=cwd,
            default_mqtt_prefix="mqtt/weather-cal",
        )

        # ---- weather ----
        weather_service = get_prop_by_keys(config, "weather", "service", required=True)
        _supported = registered_services()
        if weather_service not in _supported:
            raise ConfigError(
                f"weather.service '{weather_service}' is not supported "
                f"(choose from: {', '.join(_supported)})"
            )

        weather_apikey = get_prop_by_keys(
            config, "weather", "apikey",
            required=needs_apikey(weather_service),
            default=None,
        )
        weather_metric = get_prop_by_keys(config, "weather", "metric", default=True)
        num_hourly_forecasts = get_prop_by_keys(
            config, "weather", "num_hourly_forecasts", default=6
        )
        if num_hourly_forecasts < 0:
            raise ConfigError(
                f"weather.num_hourly_forecasts must be non-negative (got {num_hourly_forecasts})"
            )

        # ---- google ----
        google_apikey = get_prop_by_keys(config, "google", "apikey", required=True)
        staticmaps_mapid = get_prop_by_keys(config, "google", "staticmaps_mapid", required=True)

        # ---- location ----
        location = get_prop(config, "location", required=True).strip()

        # ---- logs: the boards' log lines, kept on disk ----
        logs_path = str(get_prop_by_keys(config, "logs", "path", default="data/board-logs.db",
                                         required=False))
        logs_days = get_prop_by_keys(config, "logs", "keep_days", default=90, required=False)
        if isinstance(logs_days, bool) or not isinstance(logs_days, (int, float)) or logs_days < 0:
            raise ConfigError(f"logs.keep_days must be a number of days, 0 for no limit (got {logs_days!r})")
    except (ConfigError, KeyError) as exc:
        # KeyError comes from a required key that is absent; its arg is the
        # user-facing message.
        _err(exc.args[0] if exc.args else str(exc))

    return ServerConfig(
        core=core,
        weather_service=weather_service,
        weather_apikey=weather_apikey,
        weather_metric=weather_metric,
        num_hourly_forecasts=num_hourly_forecasts,
        google_apikey=google_apikey,
        staticmaps_mapid=staticmaps_mapid,
        location=location,
        logs_path=logs_path,
        logs_days=float(logs_days),
    )


def main():
    global log

    parser = argparse.ArgumentParser(description="Inkplate weather calendar server")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate the calendar images once and exit. "
             "Skips HTTP server, MQTT, and the refresh scheduler. "
             "Useful for iterating on templates during development.",
    )
    args = parser.parse_args()

    config_path = os.path.join(cwd, "config.yaml")
    config = load_yaml(config_path)

    debug = get_prop(config, "debug", default=False)
    log_ini_path = os.path.join(cwd, "logging.dev.ini" if debug else "logging.ini")
    logging.config.fileConfig(log_ini_path, disable_existing_loggers=False)
    log = logging.getLogger("server")
    log.info("Inkplate Weather Calendar Server version: %s", _server_version())

    cfg = validate_config(config)

    # Logging timestamps follow the process TZ, not cfg.core.server.timezone; align them.
    align_process_timezone(cfg.core.server.timezone)
    log.info(f"timezone: {cfg.core.server.timezone}")
    log.info(f"display: {cfg.core.server.schedule.describe()}")
    log.info(f"regen_lead_seconds: {cfg.core.server.regen_lead_seconds}")

    gapi = GoogleAPIService(cfg.google_apikey, os.path.join(cwd, "data", "map-cache"))

    if cfg.weather_service == "mock":
        log.info("Using mock weather service — randomised data")
    weather_svc = DeferredWeather(lambda: _create_weather_service(
        cfg.weather_service,
        apikey=cfg.weather_apikey,
        location=cfg.location,
        num_hours=cfg.num_hourly_forecasts,
        metric=cfg.weather_metric,
    ))

    geometry = cfg.core.image.page_kwargs()
    pages = [
        TodayPage(**geometry),
        CurrentPage(**geometry),
        HourlyPage(**geometry),
        DailyPage(**geometry),
        TomorrowPage(**geometry),
    ]
    # Both fetch at the first render, after the server is up. Each page
    # declares what it needs in Page.requires.
    source = CompositeSource(StaticMapSource(gapi, cfg.staticmaps_mapid, cfg.location), weather_svc)

    logs_file = os.path.join(cwd, cfg.logs_path)
    os.makedirs(os.path.dirname(logs_file), exist_ok=True)
    board_logs = LogStore(logs_file, keep_days=cfg.logs_days)

    try:
        server = DisplayServer(
            pages=pages,
            source=source,
            schedule=cfg.core.server.schedule,
            tz=cfg.core.server.timezone,
            regen_lead_seconds=cfg.core.server.regen_lead_seconds,
            port=cfg.core.server.port,
            https_port=cfg.core.server.https_port,
            certificate_dir=os.path.join(cwd, "data", "certificate"),
            mqtt=cfg.core.mqtt,
            mqtt_client_id=f"eink-cal-server-{socket.gethostname()}",
            firmware=cfg.core.firmware,
            network=cfg.core.network,
            install_boards=INSTALL_BOARDS,
            settings_url="settings",
            login_url="login",
            client_logs=board_logs,
            queries={"logs": LogsQuery(board_logs, cfg.core.server.timezone).answer},
        )
    except ValueError as exc:
        # The schedule names a page that does not exist. Report it like every
        # other config error rather than as a traceback.
        log.error(str(exc))
        sys.exit(1)
    login = Login(os.environ.get(PASSWORD_ENV, ""), os.path.join(cwd, "data", "login.json"))
    if not login.on:
        log.warning("no password: anyone who can reach the server can change its settings. "
                    "Set %s to turn on sign-in", PASSWORD_ENV)
    guard(server.app, login, SITE, cfg.core.server.reverse_proxy)
    server.app.register_blueprint(settings_blueprint(config_path, server, login, cfg.core.mqtt.enabled))
    server.run(once=args.once)


if __name__ == "__main__":
    main()
