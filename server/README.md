# Inkplate 10 Weather Calendar Server

A service for the weather calendar client written in Python3, backed by [Airium](https://pypi.org/project/airium/) and [Chromedriver](https://chromedriver.chromium.org/downloads).

- Uses [Accuweather](https://developer.accuweather.com/) or [OpenWeatherMap](https://openweathermap.org/api) APIs for weather data.
- Uses Google's [StaticMaps API](https://developers.google.com/maps/documentation/maps-static/overview) to generate a static map of your area.
- Uses [Airium](https://pypi.org/project/airium/) and [Chromedriver](https://chromedriver.chromium.org/downloads) to generate HTML and PNG files for image serving.
- Uses [Flask](https://flask.palletsprojects.com/en/2.3.x/) to serve images.

New to this project? Start with the [main README](../README.md) for quick start and hardware/client setup.
For local development workflows, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Before you begin

There are a few pre-requisite steps to follow to obtain to obtain your weather provider API key and your Google Static Maps ID:

- [Weather provider setup](../doc/weather-apis.md)
- [Google Static Maps setup](../doc/google-static-maps.md)

## Configuration reference

Server behavior is controlled by `server/config.yaml`.

Start by copying the example file:

```sh
cp config.example.yaml config.yaml
```

Then edit `config.yaml` with your API keys, location, and schedule.

### Configuration model

- The server reads `config.yaml` at startup.
- Most scalar keys can be overridden by environment variables. See [section on this](#configuration-via-environment-variables) below.
- `display_schedule` is a mapping and should be configured in YAML (not env vars).
- If `display_schedule` is omitted, it defaults to a single wake: `09:00:00 -> today.png`.

### Parameters

| Key | Type | Default | What it does |
|---|---|---|---|
| `server.port` | integer | `8080` | HTTP port to bind. |
| `server.timezone` | string (IANA timezone) | `Europe/Dublin` in example | Timezone used to interpret `display_schedule`; handles DST transitions server-side. |
| `server.regen_lead_seconds` | integer | `120` | Seconds before each scheduled wake when the server regenerates the target image. |
| `display_schedule` | mapping `HH:MM:SS -> endpoint` | `{"09:00:00": "today.png"}` if omitted | Defines which image to serve at each client wake time. |
| `weather.service` | string enum | `accuweather` | Weather provider (`accuweather`, `openweathermap`, or `mock`). Custom providers can be added — see [weather/README.md](weather/README.md). |
| `weather.apikey` | string | `XXXX` placeholder | Weather provider API key. |
| `weather.num_hourly_forecasts` | integer | `9` | Number of hourly forecast points to include in the hourly day view. |
| `weather.metric` | boolean | `true` | Unit system toggle for weather values. |
| `google.apikey` | string | `XXXX` placeholder | Google API key used for Static Maps requests. |
| `google.staticmaps_mapid` | string | `XXXX` placeholder | Google Static Maps Map ID. |
| `location` | string | `Dublin` | Location query used for weather and map generation. |
| `image.width` | integer | `825` | Output image width in pixels. Do not modify unless not using an Inkplate10. |
| `image.height` | integer | `1200` | Output image height in pixels. Do not modify unless not using an Inkplate10. |
| `image.innerWidth` | integer | `image.width` | Inner HTML/CSS layout width in pixels. Page content is constrained inside this centered container. Must be `<= image.width`. |
| `image.innerHeight` | integer | `image.height` | Inner HTML/CSS layout height in pixels. Overflow is clipped at this boundary. Must be `<= image.height`. |
| `image.innerAlignX` | string enum | `center` | Horizontal alignment for inner bounds inside the output canvas (`left`, `center`, `right`). |
| `image.innerAlignY` | string enum | `center` | Vertical alignment for inner bounds inside the output canvas (`top`, `center`, `bottom`). |
| `mqtt.enabled` | boolean | `false` | Enables MQTT subscription so the server can listen for client logs. |
| `mqtt.host` | string | `localhost` | MQTT broker host. |
| `mqtt.port` | integer | `1883` | MQTT broker port. |
| `mqtt.topic` | string | `mqtt/eink-cal-client` | MQTT topic the server subscribes to for client logs. |

### Configuration via environment variables

Most scalar YAML keys can be overridden by an env var named after their path,
upper-cased and joined with `_`. For example:

| YAML key                  | Env var                    |
|---                        |---                         |
| `weather.apikey`          | `WEATHER_APIKEY`           |
| `google.apikey`           | `GOOGLE_APIKEY`            |
| `google.staticmaps_mapid` | `GOOGLE_STATICMAPS_MAPID`  |
| `location`                | `LOCATION`                 |
| `server.port`             | `SERVER_PORT`              |
| `server.timezone`         | `SERVER_TIMEZONE`          |
| `server.regen_lead_seconds` | `SERVER_REGEN_LEAD_SECONDS` |
| `mqtt.enabled`            | `MQTT_ENABLED` (`true`/`false`) |

> **Note:** `display_schedule` is a YAML mapping and cannot be set via a
> single environment variable. Use a mounted `config.yaml` (see below) to
> customise the wake schedule.

The Docker image ships with a default `config.yaml` (the example with
placeholders), so a minimal run needs only the secrets:

```sh
docker run --rm -p 8080:8080 \
  -e WEATHER_APIKEY=... \
  -e GOOGLE_APIKEY=... \
  -e GOOGLE_STATICMAPS_MAPID=... \
  -e LOCATION=Cork \
  -e SERVER_TIMEZONE=Europe/Dublin \
  weather-cal-server
```

### Mounting a custom config.yaml

To customise `display_schedule` or any other setting that cannot be expressed
as an environment variable, mount your own config file over the default one
baked into the image:

```sh
docker run --rm -p 8080:8080 \
  -v "$(pwd)/config.yaml:/app/config.yaml:ro" \
  weather-cal-server
```

Or in a Compose file:

```yaml
services:
  eink-cal-server:
    image: weather-cal-server
    ports:
      - "8080:8080"
    volumes:
      - ./config.yaml:/app/config.yaml:ro
```

## How scheduling works

The server is typically a long-running process: it generates all images at startup,
then regenerates each image shortly before its next scheduled client wake.

The schedule for regenerating the images is configured via `display_schedule` — a mapping of
`HH:MM:SS` wake times (in `server.timezone`) to the image the client should
fetch at that wake. 

The server regenerates that image `server.regen_lead_seconds`
seconds (default 120) before the wake so a fresh image is always ready.

```yaml
display_schedule:
  "08:00:00": today.png
  "12:00:00": hourly.png
  "16:00:00": daily.png
  "20:00:00": tomorrow.png
```

### Pages 
The server exposes four page endpoints, each suited to a different time of day:

| Endpoint | Layout | Best used for |
|---|---|---|
| `today.png` | Simplified — today's icon, high/low, feels-like, rain probability, map | Morning |
| `tomorrow.png` | Simplified — same layout for tomorrow's forecast | Evening |
| `hourly.png` | Detailed — hourly table: icon, temp, wind direction/speed, precipitation bars | Daytime |
| `daily.png` | Detailed — 5-day table: icon, temp range, wind, precipitation, sun hours | Afternoon / Evening |

Configure which page the client fetches at each wake time via `display_schedule` in `config.yaml`.

### Telling the client when to wake next

Each response to any image endpoint (e.g. `GET /today.png`) includes an `X-Next-Refresh-Seconds`
header: an integer number of seconds from now until the next scheduled
refresh, computed from `server.refresh_times` in the configured timezone.
The Inkplate client treats this as authoritative — it simply sets its RTC
alarm to "wake `N` seconds from now" and doesn't need its own timezone
awareness for scheduling.

```sh
$ curl -sI http://localhost:8080/today.png | grep -i x-next-refresh
x-next-refresh-seconds: 17602
```

All daylight-saving / timezone math happens server-side. If the client is
unreachable when a refresh fires, it'll still wake on its next scheduled
attempt using the last seconds value it received (or the firmware's built-in
fallback on cold boot).

## Adjusting the inner frame

Inner frame settings are useful whenever your usable display area is smaller than the full 825x1200 Inkplate10 panel, or when you intentionally want a "safe" content zone inside the panel.

Common use cases:

- Picture frame + photo mat: the visible window is smaller than the physical e-paper panel.
- Edge masking and mount tolerances: bezels, adhesive borders, or slight physical misalignment can hide a few pixels near one or more edges.

The inner frame settings let you render content only inside that safe area while still generating a full-size image for the panel.

How it works:

- The output image is still generated at `image.width` x `image.height`.
- Layout content is constrained to an inner HTML/CSS frame defined by `image.innerWidth` and `image.innerHeight`.
- Anything outside the inner frame is clipped.
- `image.innerAlignX` and `image.innerAlignY` control where the inner frame sits inside the full panel.

This means you can tune the forecast layout to fit exactly inside your photo mat window without changing hardware resolution.

Example: centered inner frame smaller than the panel

```yaml
image:
  width: 825
  height: 1200
  innerWidth: 760
  innerHeight: 1060
  innerAlignX: center
  innerAlignY: center
```

Example: top-aligned frame (useful when the mat crops mostly at the bottom)

```yaml
image:
  width: 825
  height: 1200
  innerWidth: 760
  innerHeight: 1060
  innerAlignX: center
  innerAlignY: top
```

Tips:

- Start by measuring the visible mat opening in pixels relative to your rendered image.
- Keep `innerWidth <= width` and `innerHeight <= height`.
- Keep reducing inner bounds until no critical content is hidden by the mat.
- Use `python3 server.py --once` to iterate quickly while tuning values.

## MQTT

MQTT stands for Message Queuing Telemetry Transport. It is a lightweight publish/subscribe protocol that uses a broker to relay messages between devices and services.

In this project, the Inkplate client publishes its logs to an MQTT topic and the server subscribes to that topic so the logs are collected alongside the server's own output. Without MQTT enabled, debugging client issues usually means connecting the device to a development machine and watching the serial console directly.

An example of server logs with captured client logs from the MQTT topic:
```
2026-05-27 08:28:00 - simplified - INFO - Rendering today page for 2026-05-27
2026-05-27 08:28:03 - simplified - INFO - Screenshot captured and saved to file.
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:07-00:00 - NOTICE - ##### Inkplate10 Weather Calendar boot #78 #####
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:07-00:00 - INFO - battery voltage: 4.21v
2026-05-27 08:30:11 - werkzeug - INFO - 192.168.1.181 - - [27/May/2026 08:30:11] "GET /today.png HTTP/1.1" 200 -
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:07-00:00 - INFO - approx battery capacity: 98%
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:07-00:00 - INFO - connecting to WiFi SSID VM6088281...
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - configuring network time and RTC...
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - configuring remote MQTT logging...
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - connected to MQTT broker roci.local:1883
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - downloading file at URL http://roci.local:8081/today.png
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - received header X-Next-Refresh-Seconds: 3588
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - received header X-Next-URL: http://roci.local:8081/hourly.png
2026-05-27 08:30:11 - client - INFO - 2026-05-27T08:30:11-00:00 - INFO - next refresh in 3588 seconds
```

### How this project uses MQTT

- The client publishes logs using the `mqtt_logger.*` settings in the client `config.yaml`.
- The server subscribes using the `mqtt.*` settings in the server `config.yaml`.
- Both sides must point at the same broker and use the same topic.
- The default topic in this repository is `mqtt/eink-cal-client`.

### Deploying a broker

The simplest way to get started is to run [eclipse-mosquitto](https://hub.docker.com/_/eclipse-mosquitto) as a local broker.

For a development setup, create a small `mosquitto.conf` like this:

```conf
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest stdout
```

Then deploy it with Docker Compose:

```yaml
services:
  mqtt-broker:
    image: eclipse-mosquitto:2
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - mosquitto-data:/mosquitto/data
      - mosquitto-log:/mosquitto/log

volumes:
  mosquitto-data:
  mosquitto-log:
```

If you are running the server and client in Docker or on different machines, make sure both point to the broker hostname or IP address and that port `1883` is reachable.

## Local development and runtime behavior

For full local development setup (Python dependencies, local config, Chrome/Selenium), see [CONTRIBUTING.md](../CONTRIBUTING.md#server-development-setup).

From the `server` directory, run:

```sh
python3 server.py
```

For development, render images once and exit without starting HTTP/scheduler:

```sh
python3 server.py --once
```

Send `SIGTERM` (Ctrl-C) for a clean shutdown.
