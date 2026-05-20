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
from views.hourly import HourlyPage
from views.today import TodayPage
from views.daily import DailyPage
from views.tomorrow import TomorrowPage
from google.api import GoogleAPIService
from werkzeug.serving import make_server
from flask import Flask, make_response, send_file, abort
from datetime import datetime, timedelta, date as _date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

cwd = os.path.dirname(os.path.realpath(__file__))
log = logging.getLogger("server")

app = Flask(__name__)
server_display_schedule = []  # sorted (time_str, url_path) tuples; drives both regen and client wakes
server_regen_lead_seconds = 120  # seconds before wake time at which the server regenerates the image
server_tz = None
# Serialises today.png/daily.png writes (regenerate) against reads (serve handlers).
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
    display_schedule: Any        # sorted (time_str, url_path) tuples; drives both regen and client wakes
    regen_lead_seconds: Any    # int; seconds before wake time to regenerate the image
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
    regen_lead_seconds = get_prop_by_keys(config, "server", "regen_lead_seconds", default=120)
    if not isinstance(regen_lead_seconds, int) or regen_lead_seconds < 0:
        _err("server.regen_lead_seconds must be a non-negative integer (seconds)")

    raw_schedule = get_prop_by_keys(config, "display_schedule",
                                    default={"09:00:00": "today.png"})
    if not isinstance(raw_schedule, dict) or not raw_schedule:
        _err("display_schedule must be a non-empty mapping of HH:MM:SS times to image filenames")
    _validate_time_list("display_schedule", list(raw_schedule.keys()))
    display_schedule = sorted(
        [(str(t).strip(), str(p).strip()) for t, p in raw_schedule.items()],
        key=lambda x: x[0],
    )

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
        display_schedule=display_schedule,
        regen_lead_seconds=regen_lead_seconds,
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
    log_ini_path = os.path.join(cwd, "logging.ini")
    if debug:
        logging.config.fileConfig(os.path.join(cwd, "logging.dev.ini"))
    logging.config.fileConfig(log_ini_path)
    log = logging.getLogger("server")

    cfg = validate_config(config)

    # Set module-level state used by the request handler and scheduler.
    server_display_schedule = cfg.display_schedule
    server_regen_lead_seconds = cfg.regen_lead_seconds
    server_tz = cfg.timezone

    # Align the process timezone so Python's logging timestamps (which use
    # time.localtime) match the configured zone rather than UTC.
    tz_key = getattr(server_tz, "key", None)
    if tz_key:
        os.environ["TZ"] = tz_key
        time.tzset()

    log.info(f"timezone: {server_tz}")
    log.info(f"display_schedule: {server_display_schedule}")
    log.info(f"regen_lead_seconds: {server_regen_lead_seconds}")

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

    today_page = TodayPage(cfg.image_width, cfg.image_height)
    hourly_page = HourlyPage(cfg.image_width, cfg.image_height)
    daily_page = DailyPage(cfg.image_width, cfg.image_height)
    tomorrow_page = TomorrowPage(cfg.image_width, cfg.image_height)

    def regenerate(image_name=None, force_refresh=False):
        """Regenerate one or more page images.

        image_name:    'today.png', 'hourly.png', 'daily.png', 'tomorrow.png',
                       or None to regenerate all.
        force_refresh: if True, bypass any cached weather data before fetching.
        """
        regen_today    = image_name is None or image_name == "today.png"
        regen_hourly   = image_name is None or image_name == "hourly.png"
        regen_daily    = image_name is None or image_name == "daily.png"
        regen_tomorrow = image_name is None or image_name == "tomorrow.png"
        with regen_lock:
            label = image_name if image_name else "all images"
            log.info(f"Regenerating {label}")
            if force_refresh:
                weather_svc.invalidate_forecast_cache()
            daily_summary = None
            if regen_today:
                current_conditions = weather_svc.get_current_conditions()
                today_page.template(
                    map_url=map_url,
                    current_conditions=current_conditions,
                )
                today_page.save()
            if regen_hourly or regen_daily or regen_tomorrow:
                daily_summary = weather_svc.get_daily_summary()
            if regen_hourly:
                hourly_forecasts = weather_svc.get_hourly_forecast()
                hourly_page.template(
                    map_url=map_url,
                    daily_summary=daily_summary,
                    hourly_forecasts=hourly_forecasts,
                )
                hourly_page.save()
            if regen_daily or regen_tomorrow:
                five_day_forecasts = weather_svc.get_5day_forecast()
                if regen_daily:
                    daily_page.template(
                        map_url=map_url,
                        daily_summary=daily_summary,
                        daily_forecasts=five_day_forecasts,
                    )
                    daily_page.save()
                if regen_tomorrow:
                    tomorrow_date = _date.today() + timedelta(days=1)
                    tomorrow_fc = next(
                        (f for f in five_day_forecasts if f["dt"].date() == tomorrow_date),
                        None,
                    )
                    if tomorrow_fc is not None:
                        tomorrow_page.template(
                            map_url=map_url,
                            tomorrow_forecast=tomorrow_fc,
                        )
                        tomorrow_page.save()
                    else:
                        log.warning("No forecast data for tomorrow (%s), skipping", tomorrow_date)
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


def _next_regen(display_schedule, tz, lead_seconds=120, now=None):
    """
    Return (regen_dt, wake_dt, url_path) for the next scheduled regeneration.

    Regen fires `lead_seconds` seconds before the corresponding client wake
    time.  The strict `regen_dt > now` check ensures that after a regen fires,
    the next loop iteration advances to the following wake slot rather than
    re-triggering the same one immediately.

    All wall-clock arithmetic is anchored in `tz` so DST transitions are
    handled correctly.
    """
    if now is None:
        now = datetime.now(tz=tz)
    regen_lead = timedelta(seconds=lead_seconds)
    today = now.date()
    for time_str, url_path in display_schedule:
        t = datetime.strptime(time_str, "%H:%M:%S").time()
        wake_dt = datetime.combine(today, t, tzinfo=tz)
        regen_dt = wake_dt - regen_lead
        if regen_dt > now:
            return regen_dt, wake_dt, url_path
    tomorrow = today + timedelta(days=1)
    time_str, url_path = display_schedule[0]
    t = datetime.strptime(time_str, "%H:%M:%S").time()
    wake_dt = datetime.combine(tomorrow, t, tzinfo=tz)
    return wake_dt - regen_lead, wake_dt, url_path


def _next_wake(wake_schedule, tz, now=None):
    """
    Return (next_dt, url_path) for the next scheduled client wake.

    wake_schedule is a sorted list of (time_str, url_path) tuples.
    All wall-clock arithmetic is anchored in `tz` so DST transitions are
    handled correctly.
    """
    if now is None:
        now = datetime.now(tz=tz)
    today = now.date()
    for time_str, url_path in wake_schedule:
        t = datetime.strptime(time_str, "%H:%M:%S").time()
        dt = datetime.combine(today, t, tzinfo=tz)
        if dt > now:
            return dt, url_path
    tomorrow = today + timedelta(days=1)
    time_str, url_path = wake_schedule[0]
    t = datetime.strptime(time_str, "%H:%M:%S").time()
    return datetime.combine(tomorrow, t, tzinfo=tz), url_path


def get_next_wake():
    """
    Return (seconds_until_next_wake, url_path) for the next scheduled client
    wake. Drives the X-Next-Refresh-Seconds and X-Next-URL response headers.
    """
    global server_display_schedule, server_tz
    now = datetime.now(tz=server_tz)
    next_dt, url_path = _next_wake(server_display_schedule, server_tz, now=now)
    return max(0, int(next_dt.timestamp() - now.timestamp())), url_path


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
