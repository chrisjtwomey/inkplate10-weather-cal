#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inkplate weather calendar server.

Everything generic — HTTP routes, the EPD-Next-* headers, the regeneration
loop, the client log relay, signal handling — is epd_server.DisplayServer.
This file is the project: its config keys, its weather service, its five
pages and any mods, and one run() call.
"""

import os
import socket
import sys
import json
import threading
import argparse
import dataclasses
import logging.config

import yaml
from views.themes import DEFAULT_THEME, PAGE_TYPES, THEMES, page_class
from views.page import PICTURES, picture_windows
from battery_reminder import RemindingLogStore
from maps import MAP_PROVIDERS, MapCache, StaticMapSource, create_provider
from photos import PhotoSource, PhotoStore, photos_blueprint
from epd_server import DisplayServer, InstallBoard, LogsQuery, align_process_timezone
from epd_server.config import (ConfigError, CoreConfig, get_prop, get_prop_by_keys, load_core_config,
                               load_yaml, parse_network)
from epd_server.login import Login, guard
from epd_server.page import SkipPage
from epd_server.source import CompositeSource
from epd_server.settings_page import settings_blueprint
from mod_loader import ModError, load_mods
from settings_page import DEFAULT_DISPLAY, NETWORK_KEYS, PASSWORD_ENV, SITE, check_config, form_with_mods

cwd = os.path.dirname(os.path.realpath(__file__))
log = logging.getLogger("server")

PAGE_NAMES = PAGE_TYPES
PAGES = dict(THEMES[DEFAULT_THEME].pages)
# The pages the Photos page draws to preview each picture shape, in order of choice:
# the hourly page is not drawn when weather.num_hourly_forecasts is 0.
PREVIEW_PAGES = {"wide": ("today",), "tall": ("hourly", "daily")}


def page_previewer(geometry: dict, sources: list, preview_dir: str, renderer=None, page_classes: dict = PAGES,
                   page_words: dict | None = None):
    """A function that draws a page of a picture shape with a given picture, for
    the Photos page, into its own files so the display's pages stay as they are."""
    lock = threading.Lock()

    def preview(shape: str, picture_url: str) -> bytes:
        data = CompositeSource(*sources).datasets()
        with lock:
            for name in PREVIEW_PAGES[shape]:
                words = {"words": page_words[name]} if page_words else {}
                page = page_classes[name](**geometry, picture="photos", renderer=renderer, **words)
                page.name, page.png_dir = f"preview-{name}", preview_dir
                try:
                    page.template(**{k: picture_url if k == "photo_url" else data[k]() for k in page.requires})
                except SkipPage:
                    continue
                os.makedirs(preview_dir, exist_ok=True)
                page.save()
                with open(page.png_path, "rb") as f:
                    return f.read()
        raise LookupError(shape)

    return preview

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
    map_provider: str         # one of MAP_PROVIDERS
    google_apikey: str | None   # set when map_provider is google
    staticmaps_mapid: str | None
    geoapify_apikey: str | None  # set when map_provider is geoapify
    location: str
    pictures: dict[str, str]  # page name -> one of PICTURES
    page_themes: dict[str, str]  # page type -> a theme in views.themes.THEMES
    logs_path: str            # the boards' log lines, relative to this folder
    logs_days: float          # how long a line is kept


def load_settings(config: dict) -> ServerConfig:
    """Parse the raw config dict, apply defaults, and validate all values.

    The generic blocks (server, image, mqtt, display, debug) are
    validated by epd_server.config.load_core_config. This function adds the
    keys only this project has (weather, map, google, geoapify, location).

    Raises:
        ConfigError, KeyError: a value is wrong, or a required key is absent.
    """
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
    if isinstance(num_hourly_forecasts, bool) or not isinstance(num_hourly_forecasts, int) \
            or num_hourly_forecasts < 0:
        raise ConfigError(
            f"weather.num_hourly_forecasts must be non-negative (got {num_hourly_forecasts!r})"
        )

    # ---- map ----
    map_provider = get_prop_by_keys(config, "map", "provider", default="google", required=False)
    if map_provider not in MAP_PROVIDERS:
        raise ConfigError(
            f"map.provider '{map_provider}' is not supported (choose from: {', '.join(MAP_PROVIDERS)})"
        )
    on_google = map_provider == "google"
    google_apikey = get_prop_by_keys(config, "google", "apikey", required=on_google, default=None)
    staticmaps_mapid = get_prop_by_keys(config, "google", "staticmaps_mapid", required=on_google, default=None)
    geoapify_apikey = get_prop_by_keys(config, "geoapify", "apikey", required=map_provider == "geoapify",
                                       default=None)

    # ---- location ----
    location = get_prop(config, "location", required=True)
    if not isinstance(location, str):
        raise ConfigError(f"location must be a place name, in quotes if it is a number (got {location!r})")
    location = location.strip()

    # ---- picture: the map or today's photo, for each page ----
    pictures = get_prop(config, "picture", required=False, default=None) or {}
    if not isinstance(pictures, dict):
        raise ConfigError(f"picture must name pages, such as today: photos (got {pictures!r})")
    for page, picture in pictures.items():
        if page not in PAGE_NAMES:
            raise ConfigError(f"picture.{page}: no such page (choose from: {', '.join(PAGE_NAMES)})")
        if picture not in PICTURES:
            raise ConfigError(f"picture.{page} must be map or photos (got {picture!r})")

    # ---- pages: each page type's theme ----
    pages = get_prop(config, "pages", required=False, default=None) or {}
    if not isinstance(pages, dict):
        raise ConfigError(f"pages must name page types, such as today: {{theme: classic}} (got {pages!r})")
    page_themes = {}
    for page_type in PAGE_TYPES:
        block = pages.get(page_type) or {}
        if not isinstance(block, dict):
            raise ConfigError(f"pages.{page_type} must hold settings, such as theme: classic (got {block!r})")
        theme = block.get("theme", DEFAULT_THEME)
        if theme not in THEMES:
            raise ConfigError(f"pages.{page_type}.theme {theme!r} does not exist (choose from: {', '.join(THEMES)})")
        if page_type not in THEMES[theme].pages:
            raise ConfigError(f"pages.{page_type}.theme {theme!r} has no {page_type} page")
        page_themes[page_type] = theme
    unknown = sorted(set(pages) - set(PAGE_TYPES))
    if unknown:
        raise ConfigError(f"pages.{unknown[0]}: no such page (choose from: {', '.join(PAGE_TYPES)})")

    # ---- logs: the boards' log lines, kept on disk ----
    logs_path = str(get_prop_by_keys(config, "logs", "path", default="data/board-logs.db",
                                     required=False))
    logs_days = get_prop_by_keys(config, "logs", "keep_days", default=90, required=False)
    if isinstance(logs_days, bool) or not isinstance(logs_days, (int, float)) or logs_days < 0:
        raise ConfigError(f"logs.keep_days must be a number of days, 0 for no limit (got {logs_days!r})")

    return ServerConfig(
        core=core,
        weather_service=weather_service,
        weather_apikey=weather_apikey,
        weather_metric=weather_metric,
        num_hourly_forecasts=num_hourly_forecasts,
        map_provider=map_provider,
        google_apikey=google_apikey,
        staticmaps_mapid=staticmaps_mapid,
        geoapify_apikey=geoapify_apikey,
        location=location,
        pictures={page: pictures.get(page, "map") for page in PAGE_NAMES},
        page_themes=page_themes,
        logs_path=logs_path,
        logs_days=float(logs_days),
    )


def validate_config(config: dict) -> ServerConfig:
    """The settings in ``config``. Logs a clear error and exits on any invalid
    value rather than letting a bad entry surface as an obscure exception later."""
    try:
        return load_settings(config)
    except (ConfigError, KeyError) as exc:
        # KeyError comes from a required key that is absent; its arg is the
        # user-facing message.
        log.error(exc.args[0] if exc.args else str(exc))
        sys.exit(1)


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

    map_cache = MapCache(create_provider(cfg.map_provider, google_apikey=cfg.google_apikey,
                                         staticmaps_mapid=cfg.staticmaps_mapid,
                                         geoapify_apikey=cfg.geoapify_apikey),
                         os.path.join(cwd, "data", "map-cache"))

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
    page_classes = {name: page_class(cfg.page_themes[name], name) for name in PAGE_TYPES}
    page_words = {name: THEMES[cfg.page_themes[name]].words for name in PAGE_TYPES}
    pages = [page_classes[name](**geometry, picture=cfg.pictures[name], words=page_words[name]) for name in PAGE_TYPES]
    photo_store = PhotoStore(os.path.join(cwd, "data", "photos"))
    # Each fetches at the first render that needs it, after the server is up.
    # Each page declares what it needs in Page.requires.
    photo_source = PhotoSource(photo_store)
    sources = [StaticMapSource(map_cache, cfg.location), weather_svc, photo_source]
    try:
        mods = load_mods(os.path.join(cwd, "mods"), os.path.join(cwd, "data", "mods"), config, geometry, pages, sources)
    except ModError as exc:
        log.exception(str(exc))
        sys.exit(1)

    logs_file = os.path.join(cwd, cfg.logs_path)
    os.makedirs(os.path.dirname(logs_file), exist_ok=True)
    board_logs = RemindingLogStore(logs_file, prefix=cfg.core.mqtt.prefix, mqtt_client=lambda: server.mqtt_client,
                                   keep_days=cfg.logs_days)

    try:
        server = DisplayServer(
            pages=mods.pages,
            source=mods.source,
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

    served = {page.png_filename for page in mods.pages}

    def take_network(text: str) -> None:
        server.network = parse_network(yaml.safe_load(text))

    server.app.register_blueprint(settings_blueprint(
        form_with_mods(mods.groups), config_path, lambda text: check_config(text, load_settings, served), login=login,
        live_keys=NETWORK_KEYS, take_live=take_network, links=(("photos", "Photos"), ("install", "Install firmware")),
        password_env=PASSWORD_ENV))
    image = cfg.core.image
    server.app.register_blueprint(photos_blueprint(
        photo_store, picture_windows(image.inner_width, image.inner_height),
        page_previewer(geometry, sources, os.path.join(cwd, "data", "photos", "previews"),
                       page_classes=page_classes, page_words=page_words),
        photo_source.today_and_tomorrow))
    server.run(once=args.once)


if __name__ == "__main__":
    main()
