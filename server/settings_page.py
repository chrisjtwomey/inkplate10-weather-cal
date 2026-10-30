"""This server's settings: every key in config.yaml, on epd's settings page, and
the sign-in's choices.
"""
from __future__ import annotations

import yaml
from epd_server.config_file import twice
from epd_server.login import SignInSite
from epd_server.settings_form import Field, Form, Group, Tab, host_zone

PASSWORD_ENV = "WEATHER_CAL_PASSWORD"
SITE = SignInSite("weather-cal", data=frozenset({"/network.bin", "/logs"}), home="/settings")

# One wake a day when config.yaml has no display block.
DEFAULT_DISPLAY = {"pools": {"today": ["today.png"]},
                   "schedule": {"type": "times", "09:00:00": "today"}}

PROVIDERS = (("accuweather", "AccuWeather"), ("meteireann", "Met Éireann"),
             ("openmeteo", "Open-Meteo"), ("openweathermap", "OpenWeatherMap"),
             ("mock", "Made-up weather"))
PROVIDERS_WITH_A_KEY = "accuweather|openweathermap"
ALIGN_X = (("left", "Left"), ("center", "Centre"), ("right", "Right"))
ALIGN_Y = (("top", "Top"), ("center", "Centre"), ("bottom", "Bottom"))

NETWORK_FIELDS = (
    Field("client.server_url", "Server address", "Boards get this address when installing firmware.",
          hint="http://weather.local:8080",
          refused="Enter it as http://host:port, with nothing after the port."),
    Field("client.wifi.ssid", "Wi-Fi name", refused="Too long. A Wi-Fi name has at most 32 characters."),
    Field("client.wifi.password", "Wi-Fi password", "8 to 63 characters.", "secret",
          refused="Enter 8 to 63 characters."),
    Field("client.mqtt_host", "MQTT broker", "The address boards reach the broker at.",
          when="mqtt.enabled=true", refused="Enter the name or address alone. The port is on the Logs tab."),
)

TABS = (
    Tab("server", "Server", (
        Group("Network", (
            Field("server.port", "Port", "", "int", 8080, minimum=1, maximum=65535),
            Field("server.https_port", "HTTPS port", "For the install page. 0 = off.", "int", 8443,
                  minimum=0, maximum=65535, refused="Port and HTTPS port cannot be the same."),
            Field("server.reverse_proxy", "Reverse proxy",
                  "Turn on if a proxy such as Caddy or nginx passes requests to this server.", "bool", False),
        )),
        Group("Pages", (
            Field("server.timezone", "Time zone", "The wake times below are in this zone.", "zone",
                  lambda cfg: host_zone()),
            Field("server.regen_lead_seconds", "Drawing time", "How long before each wake a page is drawn.",
                  "int", 120, unit="seconds", minimum=0),
        )),
    )),
    Tab("display", "Display", (
        Group("Pages", (
            Field("display.pools", "Sets", "Each set is a list of pages, shown in turn.", "pools", env=False),
            Field("display.schedule", "Wake times", "When the display wakes, and which set it shows.",
                  "times", DEFAULT_DISPLAY["schedule"], env=False),
        )),
    )),
    Tab("weather", "Weather", (
        Group("Forecast", (
            Field("location", "Location", "Such as Dublin or Cork,IE."),
            Field("weather.service", "Provider", "", "choice", choices=PROVIDERS),
            Field("weather.apikey", "API key", "", "secret", when=f"weather.service={PROVIDERS_WITH_A_KEY}"),
            Field("weather.num_hourly_forecasts", "Hours", "How many hours the hourly page shows.", "int", 6,
                  minimum=0),
            Field("weather.metric", "Metric units", "", "bool", True),
        )),
        Group("Map", (
            Field("google.apikey", "Google API key", "", "secret"),
            Field("google.staticmaps_mapid", "Map ID", "For the map's style."),
        )),
    )),
    Tab("image", "Image", (
        Group("Page size", (
            Field("image.width", "Width", "", "int", 825, unit="pixels", minimum=1),
            Field("image.height", "Height", "", "int", 1200, unit="pixels", minimum=1),
        )),
        Group("Content area", (
            Field("image.innerWidth", "Width", "", "int", lambda cfg: _image(cfg, "width", 825), unit="pixels",
                  minimum=1, long="Content width"),
            Field("image.innerHeight", "Height", "", "int", lambda cfg: _image(cfg, "height", 1200), unit="pixels",
                  minimum=1, long="Content height"),
            Field("image.innerAlignX", "Across", "", "choice", "center", choices=ALIGN_X),
            Field("image.innerAlignY", "Down", "", "choice", "center", choices=ALIGN_Y),
        )),
    )),
    Tab("firmware", "Firmware", (
        Group("Updates", (
            Field("client.firmware.enabled", "Offer updates", "The install page needs this on.", "bool", False),
            Field("client.firmware.dir", "Folder", "Images are in builds/nocard or builds/sdcard in the server image.",
                  default="firmware"),
            Field("client.firmware.offer_dev_builds", "Offer test builds", "For a bench board only.", "bool", False),
        )),
        Group("From GitHub", (
            Field("client.firmware.source.github", "Repository", "As owner/repo. Leave blank to copy images yourself.",
                  hint="chrisjtwomey/inkplate10-weather-cal"),
            Field("client.firmware.source.asset", "Asset", "", default="firmware.bin",
                  when="client.firmware.source.github=*"),
            Field("client.firmware.source.poll_seconds", "Check every", "", "int", 3600, unit="seconds", minimum=1,
                  when="client.firmware.source.github=*"),
            Field("client.firmware.source.token", "Token", "For a private repository.", "secret",
                  when="client.firmware.source.github=*"),
        )),
    )),
    Tab("logs", "Logs", (
        Group("MQTT", (
            Field("mqtt.enabled", "Take the display's log", "", "bool", False),
            Field("mqtt.host", "Broker", "", default="localhost", when="mqtt.enabled=true"),
            Field("mqtt.port", "Port", "", "int", 1883, minimum=1, maximum=65535, when="mqtt.enabled=true",
                  long="Broker port"),
            Field("mqtt.prefix", "Topic prefix", "", default="mqtt/weather-cal", when="mqtt.enabled=true"),
        )),
        Group("Kept lines", (
            Field("logs.path", "File", "", default="data/board-logs.db"),
            Field("logs.keep_days", "Keep", "0 keeps them all.", "number", 90, unit="days", minimum=0),
        )),
    )),
    Tab("install", "Install", (
        Group("What a new display gets", NETWORK_FIELDS,
              about="Written to a display when you install firmware over USB."),
    )),
)

FORM = Form(TABS)
NETWORK_KEYS = frozenset(f.key for f in NETWORK_FIELDS)


def _image(cfg: dict, key: str, default: int) -> int:
    image = cfg.get("image")
    return image.get(key, default) if isinstance(image, dict) else default


def check_config(text: str, load) -> None:
    """Refuse ``text``, with the problem, unless ``load`` would start the server on it.

    Raises:
        ValueError: it is not YAML, writes a key twice, or ``load`` refuses it.
    """
    try:
        config = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"It is not YAML: {exc}") from None
    doubled = twice(text)
    if doubled:
        raise ValueError(doubled)
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError("The top level must be a mapping.")
    try:
        load(config)
    except Exception as exc:  # noqa: BLE001 - the same error at start would stop the server
        raise ValueError(exc.args[0] if exc.args else repr(exc)) from None
