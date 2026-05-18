# Inkplate 10 Weather Calendar Server

A service for the weather calendar client written in Python3, backed by [Airium](https://pypi.org/project/airium/) and [Chromedriver](https://chromedriver.chromium.org/downloads).



Example 1                  | Example 2                 | Example 3
:-------------------------:|:-------------------------:|:-------------------------:
<img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/c37e6b65-a226-40d7-b1c7-cb3d72973054 width=300 /> | <img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/71958bcb-839d-447a-b671-a4cb5fbca25e width=300 /> | <img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/90608c9f-c16e-4d56-9edc-13b9d85ef659 width=300 />

<img width="1044" alt="Screenshot 2023-05-17 at 01 07 53" src="https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/e02e672b-7ad0-431d-8a29-c2740857a4d7">



- Uses [Accuweather](https://developer.accuweather.com/) or [OpenWeatherMap](https://openweathermap.org/api) APIs for weather data.
- Uses Google's [StaticMaps API](https://developers.google.com/maps/documentation/maps-static/overview) to generate a static map of your area.
- Uses [Airium](https://pypi.org/project/airium/) and [Chromedriver](https://chromedriver.chromium.org/downloads) to generate HTML and PNG files for image serving.
- Uses [Flask](https://flask.palletsprojects.com/en/2.3.x/) to serve images.

## Setup 

### Accuweather API

In order to obtain an API Key, you will need to:
1. Sign up to [developer.accuweather.com](https://developer.accuweather.com/).
2. Create an app in [https://developer.accuweather.com/user/me/apps](https://developer.accuweather.com/user/me/apps).
3. Enter some details about the app's usage and purpose.
4. Generate API key.

Make sure you update the config `weather.apikey` with your generated api key and update `weather.service` to `accuweather`.

### OpenWeatherMap API

In order to obtain an API Key, you will need to sign up to OpenWeatherMap and [generate an API key](https://home.openweathermap.org/api_keys).

Make sure you update the config `weather.apikey` with your generated api key and update `weather.service` to `openweathermap`.

### Google StaticMaps API

<img src="https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/b3f2efd0-23c0-4b9f-81e6-5684fc470ecc" width="800" />

In order to generate a static map of your area you will need to sign up to [Google's developer console](https://developers.google.com/):

1. Create a new project.
2. Go to Google Maps Platform → `Maps Static API` → `Enable`.
3. Go to `Credentials` → `Create Credentials` → `API Key`
4. After generating your API key, copy and update `google.apikey` in `config.yaml`
5. (Optional) add restriction to API Key and limit only to the `Maps Static API` service.

This will give us access to the Static Maps API service. In order to re-create the static map in the picture above, we first need to create a map style:

1. In Google Maps Platform → `Map styles` → `Create style`
2. In order to replicate the style used above, select `Import JSON` and paste the contents of [map-style.json](google/staticmaps/map-style.json) into the text field. This should replicate the map style I use.
3. Click `Save` and assign a name to the map style.

You can now use the map style to create a map ID that we can reference in our server:

1. In Google Maps Platform → `Map management` → `Create Map ID`.
2. Give the Map ID a name and make sure `map type` is set to `static`, then click `Save`.
3. Update the `associated map style` to the name of the map style created in the steps earlier.
4. Copy the `Map ID` and update the `google.staticmaps_id` field in `config.yaml`.

### Server setup

Ensure Python3 is installed on your system
```
python3 --version
Python 3.9.2
```

Download project and install dependencies
```
git clone https://github.com/chrisjtwomey/inkplate10-weather-cal.git
cd inkplate10-weather-cal
python3 -m pip install -r requirements.txt
```

Create your local config from the template (kept out of git):
```
cp server/config.example.yaml server/config.yaml
```
Then edit `server/config.yaml` and fill in your API keys, map ID, and location.

Run the server manually:
```
python3 server.py
```

For development — render the PNG once and exit without starting the HTTP
server or scheduler:
```
python3 server.py --once
```
The generated images land at `server/views/today.png` and `server/views/daily.png`.

The server runs as a long-running process: it generates all images at startup,
then regenerates each image shortly before its next scheduled client wake.

The schedule is configured via `display_schedule` — a mapping of
`HH:MM:SS` wake times (in `server.timezone`) to the image the client should
fetch at that wake. The server regenerates that image `server.regen_lead_seconds`
seconds (default 120) before the wake so a fresh image is always ready.

```yaml
display_schedule:
  "09:00:00": today.png
  "15:00:00": daily.png
  "21:00:00": today.png
```

Send `SIGTERM` (Ctrl-C) for a clean shutdown.

### Telling the client when to wake next

Each response to `GET /calendar.png` includes an `X-Next-Refresh-Seconds`
header: an integer number of seconds from now until the next scheduled
refresh, computed from `server.refresh_times` in the configured timezone.
The Inkplate client treats this as authoritative — it simply sets its RTC
alarm to "wake `N` seconds from now" and doesn't need its own timezone
awareness for scheduling.

```sh
$ curl -sI http://localhost:8080/calendar.png | grep -i x-next-refresh
x-next-refresh-seconds: 17602
```

All daylight-saving / timezone math happens server-side. If the client is
unreachable when a refresh fires, it'll still wake on its next scheduled
attempt using the last seconds value it received (or the firmware's built-in
fallback on cold boot).

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

Copy `config.example.yaml` as a starting point:

```sh
cp config.example.yaml config.yaml
# edit config.yaml with your API keys, location, and schedule
```

