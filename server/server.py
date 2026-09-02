#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import sys
import time
import json
import yaml
import signal
import argparse
import dataclasses
import threading
from typing import Any
import logging.config
from typing import NoReturn
from utils import get_prop, get_prop_by_keys
from epd_server.config import ConfigError, load_core_config
from epd_server.mqtt import client_log_subscriber
from epd_server.pipeline import regenerate as regenerate_pages
from epd_server.source import CompositeSource, StaticSource
from epd_server.scheduling import (
    next_regen as _next_regen,
    next_wake as _next_wake,
    seconds_until,
)
from views.hourly import HourlyPage
from views.today import TodayPage
from views.current import CurrentPage
from views.daily import DailyPage
from views.tomorrow import TomorrowPage
from google.api import GoogleAPIService
from werkzeug.serving import make_server
from flask import Flask, make_response, send_file, abort
from datetime import datetime

cwd = os.path.dirname(os.path.realpath(__file__))
log = logging.getLogger("server")

app = Flask(__name__)
server_display_schedule = []  # sorted (time_str, url_path) tuples; drives both regen and client wakes
server_regen_lead_seconds = 120  # seconds before wake time at which the server regenerates the image
server_tz = None
# Serialises today.png/daily.png writes (regenerate) against reads (serve handlers).
regen_lock = threading.Lock()
shutdown_event = threading.Event()


# Import all service modules so that their @register decorators run and
# populate the registry before validate_config() uses it.
import weather.accuweather.accuweather  # noqa: F401
import weather.openweathermap.openweathermap  # noqa: F401
import weather.mock.mock  # noqa: F401
import weather.meteireann.meteireann  # noqa: F401
import weather.openmeteo.openmeteo  # noqa: F401
from weather.registry import create as _create_weather_service, registered_services


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
    timezone: Any             # tzinfo / ZoneInfo
    display_schedule: Any        # sorted (time_str, url_path) tuples; drives both regen and client wakes
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
    mqtt_topic: Any
    debug: Any


def validate_config(config: dict) -> ServerConfig:
    """Parse the raw config dict, apply defaults, and validate all values.

    The generic blocks (server, image, mqtt, display_schedule, debug) are
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
            default_schedule={"09:00:00": "today.png"},
            default_mqtt_topic="mqtt/eink-cal-client",
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
            required=(weather_service != "mock"),
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
    except (ConfigError, KeyError) as exc:
        # KeyError comes from a required key that is absent; its arg is the
        # user-facing message.
        _err(exc.args[0] if exc.args else str(exc))

    return ServerConfig(
        port=core.server.port,
        timezone=core.server.timezone,
        display_schedule=core.server.display_schedule,
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
        mqtt_topic=core.mqtt.topic,
        debug=core.server.debug,
    )

def main():
    global log, server_display_schedule, server_regen_lead_seconds, server_tz

    parser = argparse.ArgumentParser(description="Inkplate weather calendar server")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Generate the calendar image once and exit. "
             "Skips HTTP server, MQTT, and the refresh scheduler. "
             "Useful for iterating on templates during development.",
    )
    args = parser.parse_args()

    config_file = open(os.path.join(cwd, "config.yaml"))
    config = yaml.safe_load(config_file)

    debug = get_prop(config, "debug", default=False)
    log_ini_path = os.path.join(cwd, "logging.dev.ini" if debug else "logging.ini")
    logging.config.fileConfig(log_ini_path, disable_existing_loggers=False)
    log = logging.getLogger("server")
    log.info("Inkplate Weather Calendar Server version: %s", _server_version())

    cfg = validate_config(config)

    # Set module-level state used by the request handler and scheduler.
    server_display_schedule = cfg.display_schedule
    server_regen_lead_seconds = cfg.regen_lead_seconds
    server_tz = cfg.timezone

    # Align the process timezone so Python's logging timestamps (which use
    # time.localtime) match the configured zone rather than UTC.
    tz_key = getattr(server_tz, "key", None)
    if tz_key and hasattr(time, "tzset"):
        os.environ["TZ"] = tz_key
        time.tzset()

    log.info(f"timezone: {server_tz}")
    log.info(f"display_schedule: {server_display_schedule}")
    log.info(f"regen_lead_seconds: {server_regen_lead_seconds}")

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

    today_page = TodayPage(
        cfg.image_width,
        cfg.image_height,
        cfg.image_inner_width,
        cfg.image_inner_height,
        cfg.image_inner_align_x,
        cfg.image_inner_align_y,
    )
    current_page = CurrentPage(
        cfg.image_width,
        cfg.image_height,
        cfg.image_inner_width,
        cfg.image_inner_height,
        cfg.image_inner_align_x,
        cfg.image_inner_align_y,
    )
    hourly_page = HourlyPage(
        cfg.image_width,
        cfg.image_height,
        cfg.image_inner_width,
        cfg.image_inner_height,
        cfg.image_inner_align_x,
        cfg.image_inner_align_y,
    )
    daily_page = DailyPage(
        cfg.image_width,
        cfg.image_height,
        cfg.image_inner_width,
        cfg.image_inner_height,
        cfg.image_inner_align_x,
        cfg.image_inner_align_y,
    )
    tomorrow_page = TomorrowPage(
        cfg.image_width,
        cfg.image_height,
        cfg.image_inner_width,
        cfg.image_inner_height,
        cfg.image_inner_align_x,
        cfg.image_inner_align_y,
    )

    # Every page the server serves, and where their content comes from.
    # Each page declares the datasets it needs in Page.requires; the pipeline
    # fetches each one once per regeneration and passes it to the pages that
    # asked for it. map_url is a constant, so it comes from a StaticSource.
    pages = [today_page, current_page, hourly_page, daily_page, tomorrow_page]
    source = CompositeSource(StaticSource(map_url=map_url), weather_svc)

    def regenerate(image_name=None, force_refresh=False):
        """Regenerate one page image, or all of them when image_name is None.

        force_refresh: if True, bypass any cached weather data before fetching.
        """
        with regen_lock:
            label = image_name if image_name else "all images"
            log.info(f"Regenerating {label}")
            rendered = regenerate_pages(pages, source, only=image_name,
                                        force_refresh=force_refresh)
            log.info("Regeneration complete: %s",
                     ", ".join(p.png_filename for p in rendered) or "nothing rendered")

    regenerate()

    if args.once:
        log.info("--once: generated image, exiting without starting server")
        return

    mqtt_client = None
    if cfg.mqtt_enabled:
        mqtt_client = get_client_mqtt_logging(cfg.mqtt_host, cfg.mqtt_port, cfg.mqtt_topic)

    http_server = ServerThread(app, cfg.port)
    http_server.start()

    def handle_signal(signum, _frame):
        log.info(f"Received signal {signum}, shutting down")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    while not shutdown_event.is_set():
        now = datetime.now(tz=server_tz)
        next_regen_dt, next_wake_dt, next_image = _next_regen(server_display_schedule, server_tz, lead_seconds=server_regen_lead_seconds, now=now)
        # Use timestamps (always real UTC seconds) rather than `next_dt - now`.
        # Python's datetime subtraction does naive wall-clock subtraction when
        # both sides share the same tzinfo, which silently drops the 1h shift
        # across a DST transition.
        wait_seconds = max(0.0, next_regen_dt.timestamp() - now.timestamp())
        log.info(f"Next client wake at {next_wake_dt.isoformat()} → {next_image}")
        log.info(f"Regenerating {next_image} at {next_regen_dt.isoformat()} (in {int(wait_seconds)}s)")
        if shutdown_event.wait(wait_seconds):
            break
        try:
            regenerate(image_name=next_image, force_refresh=True)
        except Exception:
            log.exception("Scheduled regeneration failed; will retry at next regen time")

    http_server.shutdown()
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

    log.info("Exited")


def get_client_mqtt_logging(host, port, topic):
    return client_log_subscriber(host, port, topic, client_id="eink-cal-server")



def get_next_wake():
    """
    Return (seconds_until_next_wake, url_path) for the next scheduled client
    wake. Drives the X-Next-Refresh-Seconds and X-Next-URL response headers.
    """
    global server_display_schedule, server_tz
    now = datetime.now(tz=server_tz)
    next_dt, url_path = _next_wake(server_display_schedule, server_tz, now=now)
    return seconds_until(now, next_dt), url_path


class ServerThread(threading.Thread):
    def __init__(self, app, port):
        threading.Thread.__init__(self, daemon=True)
        self.server = make_server("0.0.0.0", port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        log.info("Starting http server")
        self.server.serve_forever()

    def shutdown(self):
        log.info("Stopping http server")
        self.server.shutdown()


@app.route("/today.png")
def serve_today_png():
    """Returns the today (simplified forecast) image."""
    return _serve_png(os.path.join(cwd, "views/today.png"))


@app.route("/current.png")
def serve_current_png():
    """Returns the current (simplified forecast) image."""
    return _serve_png(os.path.join(cwd, "views/current.png"))

@app.route("/tomorrow.png")
def serve_tomorrow_png():
    """Returns the tomorrow (simplified forecast) image."""
    return _serve_png(os.path.join(cwd, "views/tomorrow.png"))

@app.route("/hourly.png")
def serve_hourly_png():
    """Returns the hourly (detailed forecast) image."""
    return _serve_png(os.path.join(cwd, "views/hourly.png"))

@app.route("/daily.png")
def serve_daily_png():
    """Returns the daily (5-day detailed forecast) image."""
    return _serve_png(os.path.join(cwd, "views/daily.png"))


def _serve_png(path):
    """
    Serve a PNG file, blocking while any regeneration is in progress so we
    never serve a partial write.

    Sets X-Next-Refresh-Seconds and X-Next-URL from the wake schedule so the
    client knows when to next wake and which endpoint to fetch.
    """
    from flask import request

    if not os.path.exists(path):
        log.error(f"{path}: no such file exists")
        abort(404)

    with regen_lock:
        with open(path, "rb") as f:
            stream = io.BytesIO(f.read())

    seconds, url_path = get_next_wake()
    next_url = request.host_url.rstrip("/") + "/" + url_path.lstrip("/")

    rsp = make_response(send_file(
        stream,
        mimetype="image/png",
        as_attachment=True,
        download_name=os.path.basename(path),
    ))
    rsp.headers["X-Next-Refresh-Seconds"] = str(seconds)
    rsp.headers["X-Next-URL"] = next_url
    return rsp


if __name__ == "__main__":
    main()
