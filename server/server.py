#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import io
import sys
import time
import yaml
import signal
import argparse
import dataclasses
import threading
from typing import Any
import logging.config
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from utils import get_prop, get_prop_by_keys
from views.calendar import CalendarPage
from google.api import GoogleAPIService
from werkzeug.serving import make_server
from flask import Flask, make_response, send_file, abort
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

cwd = os.path.dirname(os.path.realpath(__file__))
log = logging.getLogger("server")

app = Flask(__name__)
server_regen_times = []    # when the server regenerates the calendar image
server_refresh_times = []  # when the server tells clients to wake and refresh
server_tz = None
# Serialises calendar.png writes (regenerate) against reads (serve handler).
regen_lock = threading.Lock()
shutdown_event = threading.Event()


_SUPPORTED_WEATHER_SERVICES = ("accuweather", "openweathermap", "mock")


@dataclasses.dataclass
class ServerConfig:
    # Fields are typed as Any because values come from a generic YAML/env-var
    # accessor whose return type cannot be statically narrowed.  Type safety
    # is enforced by the validation logic in validate_config(), not here.
    port: Any
    timezone: Any             # tzinfo / ZoneInfo
    regen_times: Any          # list[str] of HH:MM:SS strings
    refresh_times: Any        # list[str] of HH:MM:SS strings
    image_width: Any
    image_height: Any
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

    Logs a clear error and exits immediately on any invalid value rather than
    letting a bad entry surface as an obscure exception later at runtime.
    """
    def _err(msg: str):
        log.error(msg)
        sys.exit(1)

    # ---- weather ----
    weather_service = get_prop_by_keys(config, "weather", "service", required=True)
    if weather_service not in _SUPPORTED_WEATHER_SERVICES:
        _err(f"weather.service '{weather_service}' is not supported "
             f"(choose from: {', '.join(_SUPPORTED_WEATHER_SERVICES)})")

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
        _err(f"weather.num_hourly_forecasts must be non-negative (got {num_hourly_forecasts})")

    # ---- google ----
    google_apikey = get_prop_by_keys(config, "google", "apikey", required=True)
    staticmaps_mapid = get_prop_by_keys(config, "google", "staticmaps_mapid", required=True)

    # ---- location ----
    location = get_prop(config, "location", required=True).strip()

    # ---- server ----
    port = get_prop_by_keys(config, "server", "port", default=8080)

    refresh_times = get_prop_by_keys(config, "server", "refresh_times", default=["09:00:00"])
    if not refresh_times:
        _err("server.refresh_times must contain at least one HH:MM:SS entry")
    _validate_time_list("server.refresh_times", refresh_times)

    regen_times = get_prop_by_keys(config, "server", "regen_times", default=None, required=False)
    if not regen_times:
        regen_times = refresh_times  # default: regenerate on the same schedule
    else:
        _validate_time_list("server.regen_times", regen_times)

    tz = datetime.now().astimezone().tzinfo  # default: system local tz
    tz_name = get_prop_by_keys(config, "server", "timezone", default=None)
    if tz_name:
        try:
            tz = ZoneInfo(str(tz_name))
        except ZoneInfoNotFoundError:
            _err(f"server.timezone '{tz_name}' is not a valid IANA zone (e.g. Europe/Dublin)")

    # ---- image ----
    image_width = get_prop_by_keys(config, "image", "width", default=825)
    image_height = get_prop_by_keys(config, "image", "height", default=1200)

    # ---- mqtt ----
    mqtt_enabled = get_prop_by_keys(config, "mqtt", "enabled", default=False)
    mqtt_host = get_prop_by_keys(config, "mqtt", "host", default="localhost")
    mqtt_port = get_prop_by_keys(config, "mqtt", "port", default=1883)
    mqtt_topic = get_prop_by_keys(config, "mqtt", "topic", default="mqtt/eink-cal-client")

    # ---- debug ----
    debug = get_prop(config, "debug", default=False)

    return ServerConfig(
        port=port,
        timezone=tz,
        regen_times=regen_times,
        refresh_times=refresh_times,
        image_width=image_width,
        image_height=image_height,
        weather_service=weather_service,
        weather_apikey=weather_apikey,
        weather_metric=weather_metric,
        num_hourly_forecasts=num_hourly_forecasts,
        google_apikey=google_apikey,
        staticmaps_mapid=staticmaps_mapid,
        location=location,
        mqtt_enabled=mqtt_enabled,
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_topic=mqtt_topic,
        debug=debug,
    )


def main():
    global log, server_regen_times, server_refresh_times, server_tz

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
    log_ini_path = os.path.join(cwd, "logging.ini")
    if debug:
        logging.config.fileConfig(os.path.join(cwd, "logging.dev.ini"))
    logging.config.fileConfig(log_ini_path)
    log = logging.getLogger("server")

    cfg = validate_config(config)

    # Set module-level state used by the request handler and scheduler.
    server_refresh_times = cfg.refresh_times
    server_regen_times = cfg.regen_times
    server_tz = cfg.timezone

    # Align the process timezone so Python's logging timestamps (which use
    # time.localtime) match the configured zone rather than UTC.
    tz_key = getattr(server_tz, "key", None)
    if tz_key:
        os.environ["TZ"] = tz_key
        time.tzset()

    log.info(f"timezone: {server_tz}")
    log.info(f"regen_times (image regeneration schedule): {server_regen_times}")
    log.info(f"refresh_times (client wake schedule):      {server_refresh_times}")

    gapi = GoogleAPIService(cfg.google_apikey)
    map_url = gapi.get_static_map_url(cfg.staticmaps_mapid, cfg.location)

    if cfg.weather_service == "mock":
        from weather.mock.mock import MockWeatherService

        log.info("Using mock weather service — randomised data")
        weather_svc = MockWeatherService(
            num_hours=cfg.num_hourly_forecasts,
            metric=cfg.weather_metric,
        )
    elif cfg.weather_service == "accuweather":
        from weather.accuweather.accuweather import AccuweatherService

        weather_svc = AccuweatherService(
            cfg.weather_apikey,
            cfg.location,
            metric=cfg.weather_metric,
            num_hours=cfg.num_hourly_forecasts,
        )
    elif cfg.weather_service == "openweathermap":
        from weather.openweathermap.openweathermap import OpenWeatherMapService

        weather_svc = OpenWeatherMapService(
            cfg.weather_apikey,
            cfg.location,
            metric=cfg.weather_metric,
            num_hours=cfg.num_hourly_forecasts,
        )
    else:
        log.error(f"not a supported weather service: {cfg.weather_service}")
        sys.exit(1)

    page = CalendarPage(cfg.image_width, cfg.image_height)

    def regenerate():
        with regen_lock:
            log.info("Regenerating calendar image")
            daily_summary = weather_svc.get_daily_summary()
            hourly_forecasts = weather_svc.get_hourly_forecast()
            page.template(
                map_url=map_url,
                daily_summary=daily_summary,
                hourly_forecasts=hourly_forecasts,
            )
            page.save()
            log.info("Regeneration complete")

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
        next_regen_dt = _next_refresh_datetime(server_regen_times, server_tz, now=now)
        next_client_dt = _next_refresh_datetime(server_refresh_times, server_tz, now=now)
        # Use timestamps (always real UTC seconds) rather than `next_dt - now`.
        # Python's datetime subtraction does naive wall-clock subtraction when
        # both sides share the same tzinfo, which silently drops the 1h shift
        # across a DST transition.
        wait_seconds = max(0.0, next_regen_dt.timestamp() - now.timestamp())
        log.info(f"Next regeneration at {next_regen_dt.isoformat()} (in {int(wait_seconds)}s)")
        log.info(f"Next client refresh at {next_client_dt.isoformat()}")
        if shutdown_event.wait(wait_seconds):
            break
        try:
            regenerate()
        except Exception:
            log.exception("Scheduled regeneration failed; will retry at next regen time")

    http_server.shutdown()
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

    log.info("Exited")


def get_client_mqtt_logging(host, port, topic):
    mqtt_client = mqtt.Client(CallbackAPIVersion.VERSION2, "eink-cal-server")
    client_log = logging.getLogger("client")

    def on_connect(_client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            log.error("Connection to client logging broker failed")

        log.info("Connected to client logging broker")

    def on_disconnect(_client, _userdata, _disconnect_flags, reason_code, _properties):
        if reason_code.is_failure:
            log.error("Unexpected broker disconnection")

        log.info("Disconnected from client logging broker")

    def on_message(_client, _userdata, message):
        if message.retain:
            # ignore stale messages
            return

        client_log.info(message.payload.decode())

    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message
    try:
        mqtt_client.connect(host, port, 60)
        mqtt_client.subscribe(topic)
        mqtt_client.loop_start()

        return mqtt_client
    except Exception as e:
        log.error(f"Connection to client logging broker failed: {e}")

    return None


def _validate_time_list(config_key, times):
    """Validate that every entry in `times` is a valid HH:MM:SS string.
    Exits with an error message if any entry is malformed."""
    for t in times:
        try:
            datetime.strptime(t, "%H:%M:%S")
        except ValueError:
            log.error(
                f"{config_key}: '{t}' is not a valid time — expected HH:MM:SS "
                f"(e.g. '09:00:00')"
            )
            sys.exit(1)


def _next_refresh_datetime(refresh_times, tz, now=None):
    """
    Return the next refresh moment as a tz-aware datetime.

    All wall-clock arithmetic is anchored in `tz` so DST transitions are
    handled correctly: subtracting two tz-aware datetimes yields a real-time
    delta even when an offset change happens between them.
    """
    if now is None:
        now = datetime.now(tz=tz)
    today = now.date()
    for rt in refresh_times:
        t = datetime.strptime(rt, "%H:%M:%S").time()
        dt = datetime.combine(today, t, tzinfo=tz)
        if dt > now:
            return dt
    tomorrow = today + timedelta(days=1)
    t = datetime.strptime(refresh_times[0], "%H:%M:%S").time()
    return datetime.combine(tomorrow, t, tzinfo=tz)


def get_next_refresh_seconds():
    """
    Return seconds from now until the next scheduled refresh. Drives the
    client's deep-sleep duration via the X-Next-Refresh-Seconds header.
    The server is the single source of truth for *when* — the client just
    counts down. DST is handled here (via _next_refresh_datetime) so the
    client doesn't need timezone awareness for scheduling.
    """
    global server_refresh_times, server_tz
    now = datetime.now(tz=server_tz)
    next_dt = _next_refresh_datetime(server_refresh_times, server_tz, now=now)
    return max(0, int(next_dt.timestamp() - now.timestamp()))


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


@app.route("/calendar.png")
def serve_img_png():
    """
    Returns the calendar image directly through send_file
    """

    path = os.path.join(cwd, "views/calendar.png")

    if not os.path.exists(path):
        log.error(f"{path}: no such file exists")
        abort(404)

    # Block while a regeneration is mid-write so we never serve a partial PNG.
    with regen_lock:
        with open(path, "rb") as f:
            stream = io.BytesIO(f.read())

    rsp = make_response(send_file(
        stream,
        mimetype="image/png",
        as_attachment=True,
        download_name=os.path.basename(path),
    ))
    rsp.headers["X-Next-Refresh-Seconds"] = str(get_next_refresh_seconds())

    return rsp


if __name__ == "__main__":
    main()
