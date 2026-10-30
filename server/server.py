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
from typing import Any, NoReturn

from utils import get_prop, get_prop_by_keys
from views.hourly import HourlyPage
from views.today import TodayPage
from views.current import CurrentPage
from views.daily import DailyPage
from views.tomorrow import TomorrowPage
from google.api import GoogleAPIService
from epd_server import DisplayServer, InstallBoard, LogsQuery, LogStore, align_process_timezone
from epd_server.config import ConfigError, MqttSettings, load_core_config, load_yaml
from epd_server.login import Login, guard
from epd_server.source import CompositeSource, StaticSource
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


@dataclasses.dataclass
class ServerConfig:
    # Fields are typed as Any because values come from a generic YAML/env-var
    # accessor whose return type cannot be statically narrowed.  Type safety
    # is enforced by the validation logic in validate_config(), not here.
    port: Any
    https_port: Any           # int; the browser's install page needs HTTPS. 0 for none
    timezone: Any             # tzinfo / ZoneInfo
    schedule: Any                # WakeSchedule from the display block; drives both regen and client wakes
    regen_lead_seconds: Any    # int; seconds before wake time to regenerate the image
    image_width: Any
    image_height: Any
    image_inner_width: Any
    image_inner_height: Any
    image_inner_align_x: Any
    image_inner_align_y: Any
    weather_service: Any      # one of _SUPPORTED_WEATHER_SERVICES
    weather_apikey: Any       # str, or None for mock service
    weather_metric: Any
    num_hourly_forecasts: Any
    google_apikey: Any
    staticmaps_mapid: Any
    location: Any
    mqtt_enabled: Any
    mqtt_host: Any
    mqtt_port: Any
    mqtt_prefix: Any
    firmware: Any             # FirmwareSettings; server-driven client updates
    network: Any              # NetworkSettings; what a USB flash writes to a board
    reverse_proxy: Any        # bool; trust a proxy's X-Forwarded-* headers
    logs_path: Any            # str; the boards' log lines, relative to this folder
    logs_days: Any            # float; how long a line is kept
    debug: Any


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
        port=core.server.port,
        https_port=core.server.https_port,
        timezone=core.server.timezone,
        schedule=core.server.schedule,
        regen_lead_seconds=core.server.regen_lead_seconds,
        image_width=core.image.width,
        image_height=core.image.height,
        image_inner_width=core.image.inner_width,
        image_inner_height=core.image.inner_height,
        image_inner_align_x=core.image.inner_align_x,
        image_inner_align_y=core.image.inner_align_y,
        weather_service=weather_service,
        weather_apikey=weather_apikey,
        weather_metric=weather_metric,
        num_hourly_forecasts=num_hourly_forecasts,
        google_apikey=google_apikey,
        staticmaps_mapid=staticmaps_mapid,
        location=location,
        mqtt_enabled=core.mqtt.enabled,
        mqtt_host=core.mqtt.host,
        mqtt_port=core.mqtt.port,
        mqtt_prefix=core.mqtt.prefix,
        firmware=core.firmware,
        network=core.network,
        reverse_proxy=core.server.reverse_proxy,
        logs_path=logs_path,
        logs_days=float(logs_days),
        debug=core.server.debug,
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

    # Logging timestamps follow the process TZ, not cfg.timezone; align them.
    align_process_timezone(cfg.timezone)
    log.info(f"timezone: {cfg.timezone}")
    log.info(f"display: {cfg.schedule.describe()}")
    log.info(f"regen_lead_seconds: {cfg.regen_lead_seconds}")

    gapi = GoogleAPIService(cfg.google_apikey)
    map_url = gapi.get_static_map_local_src(cfg.staticmaps_mapid, cfg.location)

    if cfg.weather_service == "mock":
        log.info("Using mock weather service — randomised data")
    weather_svc = _create_weather_service(
        cfg.weather_service,
        apikey=cfg.weather_apikey,
        location=cfg.location,
        num_hours=cfg.num_hourly_forecasts,
        metric=cfg.weather_metric,
    )

    geometry = (
        cfg.image_width,
        cfg.image_height,
        cfg.image_inner_width,
        cfg.image_inner_height,
        cfg.image_inner_align_x,
        cfg.image_inner_align_y,
    )
    pages = [
        TodayPage(*geometry),
        CurrentPage(*geometry),
        HourlyPage(*geometry),
        DailyPage(*geometry),
        TomorrowPage(*geometry),
    ]
    # map_url is a constant, so it comes from a StaticSource; the weather
    # service supplies the rest. Each page declares what it needs in
    # Page.requires.
    source = CompositeSource(StaticSource(map_url=map_url), weather_svc)

    logs_file = os.path.join(cwd, cfg.logs_path)
    os.makedirs(os.path.dirname(logs_file), exist_ok=True)
    board_logs = LogStore(logs_file, keep_days=cfg.logs_days)

    try:
        server = DisplayServer(
            pages=pages,
            source=source,
            schedule=cfg.schedule,
            tz=cfg.timezone,
            regen_lead_seconds=cfg.regen_lead_seconds,
            port=cfg.port,
            https_port=cfg.https_port,
            certificate_dir=os.path.join(cwd, "data", "certificate"),
            mqtt=MqttSettings(cfg.mqtt_enabled, cfg.mqtt_host, cfg.mqtt_port, cfg.mqtt_prefix),
            mqtt_client_id=f"eink-cal-server-{socket.gethostname()}",
            firmware=cfg.firmware,
            network=cfg.network,
            install_boards=INSTALL_BOARDS,
            settings_url="settings",
            login_url="login",
            client_logs=board_logs,
            queries={"logs": LogsQuery(board_logs, cfg.timezone).answer},
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
    guard(server.app, login, SITE, cfg.reverse_proxy)
    server.app.register_blueprint(settings_blueprint(config_path, server, login, cfg.mqtt_enabled))
    server.run(once=args.once)


if __name__ == "__main__":
    main()
