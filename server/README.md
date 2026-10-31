# Inkplate 10 Weather Calendar Server

The server renders the display's five pages, serves them, and tells the
display when to wake next.

- Weather from AccuWeather, Met Éireann, Open-Meteo or OpenWeatherMap: [doc/weather-apis.md](../doc/weather-apis.md). To add a provider, see [weather/README.md](weather/README.md).
- A map of your area from Google's [Static Maps API](https://developers.google.com/maps/documentation/maps-static/overview): [doc/google-static-maps.md](../doc/google-static-maps.md).
- Each page is HTML, rendered to a PNG in Chrome, and served with [Flask](https://flask.palletsprojects.com/). The generic parts come from [epd](https://github.com/chrisjtwomey/epd)'s `epd-server`.

To set up a display, start with the [main README](../README.md). To work on
the server, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Configuration

The server reads `config.yaml` at start. Copy the example, then fill in your
keys, your location and your schedule:

```sh
cp config.example.yaml config.yaml
```

| Key | Default | What it does |
|---|---|---|
| `server.port` | `8080` | The HTTP port. |
| `server.timezone` | the machine's own | The IANA zone `display.schedule` is in, such as `Europe/Dublin`. |
| `server.regen_lead_seconds` | `120` | How long before each wake the server renders that wake's page. |
| `display.pools` | `today: [today.png]` | What can show. Each pool is a list of pages, shown in turn. |
| `display.schedule` | `09:00:00: today` | `type: times`, then `HH:MM:SS: pool` for each wake. |
| `weather.service` | – (required) | `accuweather`, `meteireann`, `openmeteo`, `openweathermap`, or `mock` for made-up weather. |
| `weather.apikey` | – (required, except for `meteireann`, `openmeteo` and `mock`) | The provider's API key. |
| `weather.num_hourly_forecasts` | `6` | How many hours the hourly page shows. |
| `weather.metric` | `true` | Metric units, or imperial. |
| `google.apikey` | – (required) | The Google API key, for the map. |
| `google.staticmaps_mapid` | – (required) | The map ID, for the map's style. |
| `location` | – (required) | The place to show, such as `Dublin` or `Cork,IE`. |
| `image.width`, `image.height` | `825`, `1200` | The page size in pixels: the Inkplate 10's panel, upright. |
| `image.innerWidth`, `image.innerHeight` | the page size | The area the content fits in. See [Fitting a photo mat](#fitting-a-photo-mat). |
| `image.innerAlignX`, `image.innerAlignY` | `center` | Where that area sits: `left`, `center` or `right`; `top`, `center` or `bottom`. |
| `server.https_port` | `8443` | The same routes over HTTPS, for [the install page](#the-install-page). `0` for none. |
| `client.firmware.enabled` | `false` | Offer firmware updates to the display. See [Firmware updates](#firmware-updates). |
| `client.firmware.dir` | `firmware` | The folder of `<version>.bin` images. The newest is offered. `builds/nocard`, `builds/sdcard` or `builds/timing` offers the firmware the server image carries. The install page needs `<version>.merged.bin` beside it, which those folders hold. |
| `client.firmware.product` | `inkplate10-weather-cal` | Only a display that reports this name is offered an image. |
| `client.firmware.offer_dev_builds` | `false` | Offer a display that runs a development build any other build, not only a newer one. |
| `client.firmware.source.github` | – | Fill `dir` from this repository's releases, as `owner/repo`. |
| `client.firmware.source.asset` | `firmware.bin` | The release asset to take. |
| `client.firmware.source.poll_seconds` | `3600` | How often to ask GitHub for a new release. |
| `client.firmware.source.token` | – | For a private repository. Set `CLIENT_FIRMWARE_SOURCE_TOKEN` rather than write it here. |
| `mqtt.enabled` | `false` | Take the display's log lines from an MQTT broker. See [MQTT](#mqtt). |
| `mqtt.host`, `mqtt.port` | `localhost`, `1883` | The broker. |
| `mqtt.prefix` | `mqtt/weather-cal` | The server takes every topic under `<prefix>/`; the display logs to `<prefix>/inkplate10-weather-cal`. |
| `logs.path` | `data/board-logs.db` | Where the display's log lines are kept, beside `config.yaml`. In Docker, mount a volume on `/app/data` to keep them across updates. |
| `logs.keep_days` | `90` | How many days a line is kept. `0` keeps them all. |

### Environment variables

An environment variable overrides any single key: the key's path, in capitals,
joined with `_`. `weather.apikey` is `WEATHER_APIKEY`, `server.timezone` is
`SERVER_TIMEZONE`, and `client.firmware.dir` is `CLIENT_FIRMWARE_DIR`. A
block, such as `display`, needs `config.yaml`.

`WEATHER_CAL_PASSWORD` is not a key: it sets the password for
[the Settings page](#the-settings-page-and-sign-in).

### Docker

The image holds the example `config.yaml`, so a first run needs only the
keys:

```sh
docker run -d --restart unless-stopped -p 8080:8080 \
  -e WEATHER_SERVICE=accuweather -e WEATHER_APIKEY=... \
  -e GOOGLE_APIKEY=... -e GOOGLE_STATICMAPS_MAPID=... \
  -e LOCATION="Dublin, IE" -e SERVER_TIMEZONE=Europe/Dublin \
  ghcr.io/chrisjtwomey/inkplate10-weather-cal-server:latest
```

To set the schedule or anything else in a block, mount your own
`config.yaml`, as [`docker-compose.yml`](../docker-compose.yml) does:

```sh
docker run -d --restart unless-stopped -p 8080:8080 \
  -v "$(pwd)/config.yaml:/app/config.yaml" \
  -v weather-cal-data:/app/data \
  ghcr.io/chrisjtwomey/inkplate10-weather-cal-server:latest
```

| Image tag | What it is |
|---|---|
| `latest` | Every push to main that passes CI. |
| `2.1.0-3-g62c793c` | One of those pushes, as `git describe` names it. Pin it to hold a server and its display on that build. |
| `2.1.0`, `2.1` | Releases. |

## Pages and the schedule

| Page | Shows | Suits |
|---|---|---|
| `today.png` | Today's icon, high and low, feels-like, chance of rain, and the map | Morning |
| `current.png` | The weather now, today's summary, and the map | Any time |
| `hourly.png` | The next hours: icon, temperature, wind and rain | Daytime |
| `daily.png` | The next 5 days: icon, high and low, wind, rain and sun | Afternoon |
| `tomorrow.png` | Tomorrow, in the layout of `today.png` | Evening |

`display.schedule` gives a wake time for each pool, in `server.timezone`:

```yaml
display:
  pools:
    today: [today.png]
    hourly: [hourly.png]
    daily: [daily.png]
    tomorrow: [tomorrow.png]
  schedule:
    type: times
    "08:00:00": today
    "12:00:00": hourly
    "16:00:00": daily
    "20:00:00": tomorrow
```

The server renders each page `server.regen_lead_seconds` before its wake, so
the page is ready when the display asks. Every page answer carries
`EPD-Next-Display-Refresh-Seconds`, the seconds to the next wake, and
`EPD-Next-URL`, the page to fetch then. The display sleeps for that long, so
it needs no time zone of its own; a change of the clocks is the server's
alone.

```sh
$ curl -sI http://localhost:8080/today.png | grep -i next-display-refresh
epd-next-display-refresh-seconds: 17602
```

## Fitting a photo mat

When a frame's mat hides the edges of the panel, keep the content inside the
part that shows. The page stays the panel's size; only its content moves in.

```yaml
image:
  width: 825
  height: 1200
  innerWidth: 760       # the width of the mat's opening, in pixels
  innerHeight: 1060
  innerAlignX: center
  innerAlignY: top      # for a mat that hides more at the bottom
```

- Content outside the inner area is cut off.
- `innerWidth` and `innerHeight` can be at most `width` and `height`.
- `python3 server.py --once` renders the pages without a display, to try values quickly.

## Firmware updates

With `client.firmware.enabled`, the display updates itself from the server,
with no cable.

The server image carries the firmware of its own version, in three folders:

| Folder | For |
|---|---|
| `builds/nocard` | A display without an SD card. |
| `builds/sdcard` | A display with an SD card. |
| `builds/timing` | Test work: the `nocard` build, but it wakes at least every 10 minutes, and logs at each wake when each step of the last one ended. Its version ends in `+timing`. |

Set `client.firmware.dir` to the one your display runs, with no `source`
block. The display then follows the server: a redeploy moves both.
`CLIENT_FIRMWARE_DIR` moves a display to `builds/timing` and back with a
redeploy, and no change to `config.yaml`. The move back needs
`offer_dev_builds`, since a `+timing` version is not a release: without it,
the server offers such a display only a newer build.

Two other ways to supply firmware:

- **From releases:** a `client.firmware.source` block takes `firmware.bin`, the SD card build, from each new release of this repository.
- **By hand:** copy an image into `firmware/`, named for its version, such as `firmware/v1.6.0.bin`.

What the display does with an offer:

- It takes it after it has drawn its page, while the panel shows "Installing firmware <version>" and a progress bar.
- It keeps the new firmware only once that firmware has drawn a page. Otherwise it goes back to the old one, and does not take that version again: publish a fix under a new version.
- If the install fails, it shows the last page again under the banner "Update to <version> failed".
- Below 20% battery, it waits for a charge.
- To make it check now, press RST.

A display needs one USB flash first: see the [main README](../README.md#2-set-up-the-display), or [the install page](#the-install-page). A display last flashed over USB before v2.0.0 needs one again, since v2.0.0 changed the partition table, which an update over the air cannot change.

## MQTT

With `mqtt.enabled`, the server takes the display's log lines from an MQTT
broker, logs them with its own, and keeps them. Without it, a display's log
is only on its serial port.

The display logs with its `mqtt_logger` settings ([main README](../README.md#3-settings-on-the-sd-card)), and the server listens with its `mqtt` settings. Both must name the same broker and the same prefix. The display turns Wi-Fi off before its panel refreshes, so the lines it logs after that reach only its serial port.

From a wake on 25 October 2026:

```
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:03+00:00 - NOTICE - ##### Inkplate10 boot #3 #####
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:03+00:00 - INFO - battery voltage: 4.17v
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:03+00:00 - INFO - connecting to WiFi SSID my-network...
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:04+00:00 - INFO - wifi connected in 1063 ms: 192.168.1.181
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:04+00:00 - INFO - downloading file at URL http://calendar.local:8081/today.png
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:04+00:00 - INFO - received header EPD-Next-Display-Refresh-Seconds: 3594
2026-10-25 08:30:05 - client - INFO - inkplate10-weather-cal: 2026-10-25T08:30:05+00:00 - INFO - drawing image from buffer
```

### The Settings page and sign-in

`/settings` holds every setting in `config.yaml`, in tabs. **Save and restart**
lists the changes first, checks that the server would start on them, keeps the
file's comments, keeps the old file as `config.yaml.bak`, and restarts the server.
**Restore** puts the `.bak` back. So `config.yaml` must be writable.

- API keys and passwords never reach the page. Leave one blank to keep it.
- A key an environment variable sets is locked on the page.
- A change only to the **Install** tab needs no restart.

Set `WEATHER_CAL_PASSWORD` to turn on the sign-in. A server without it logs a
warning, and anyone on the network can read the Wi-Fi password and change these
settings.

With a password set:

- `/settings`, `/install`, `/logs` and `/network.bin` need a sign-in. The
  display's own routes stay open, and so do the install page's scripts.
- The sign-in lasts 30 days. Five wrong passwords make that address wait 15 minutes.
- Other apps send the access token on the Access tab of the Settings page, to read `/logs`
  and `/network.bin`.
- Behind a reverse proxy, set `server.reverse_proxy` to `true`.

### The install page

`/install` writes the firmware and the Settings page's values to a display
over USB, from Chrome, Edge, Opera or Firefox. It needs:

- `client.firmware.enabled` set to `true`, and a `<version>.merged.bin` in
  `client.firmware.dir`.
- The server address, the Wi-Fi name and the Wi-Fi password on the Settings page's
  **Install** tab, and the MQTT broker when MQTT is on.
  The address is the one the display reaches: in Docker, the host's, not the
  container's.
- HTTPS, because a browser lets a page use a USB port only over HTTPS.
  `server.https_port`, 8443 unless set, serves every route with a certificate
  the server makes and keeps in `data/certificate`. So the browser warns about
  it once. Map the port to the same number on the host, as
  [`docker-compose.yml`](../docker-compose.yml) does. Set it to `0` behind a
  reverse proxy that has a certificate of its own. If the port is taken, the
  server logs it and runs on HTTP alone.

After it writes, the page checks that the display joins Wi-Fi, reaches the
server and, with MQTT on, reaches the broker.

Where a browser cannot be used:

```sh
curl -O http://<server>:8080/install-firmware.sh
sh install-firmware.sh display
```

With a password set, the script asks for it. With `TOKEN` set to the access
token, it does not.

### What the server keeps in `data`

Mount a volume on `/app/data`, as [`docker-compose.yml`](../docker-compose.yml)
does. It keeps these across updates:

- The display's log lines.
- The map image, in `data/map-cache`. Google counts each fetch, so with the
  volume the server fetches once per location and map ID. Without it, every
  update fetches again.
- The sign-in's keep file and the HTTPS certificate.

### When Google or the weather provider is down

The server starts anyway, and fetches at the first render. If the map cannot be
fetched, the page renders with no map, and the next render tries again. If the
weather cannot be fetched, the log says so, and the next scheduled render tries
again. Until then the server offers the pages it already made. A server that
has just updated has none, so the display shows its last page under an error
banner, and backs off.

### Reading the logs

`GET /logs` answers with the kept lines as JSON, newest last:

```sh
curl -s 'http://localhost:8080/logs?q=battery%20voltage&limit=50'
```

- `board`, `level` (that level and above) and `q` (text in the line) narrow the lines; `limit` caps them, at most 500.
- `after` or `before` a line's `id` pages forward or back.
- With a password set, send the access token from the Access tab of the Settings page: `curl -H "Authorization: Bearer <token>" ...`.

### A broker

[Eclipse Mosquitto](https://hub.docker.com/_/eclipse-mosquitto) is enough. A
`mosquitto.conf` for a home network:

```conf
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest stdout
```

And its Compose service:

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
volumes:
  mosquitto-data:
```

The display and the server must both reach the broker's host on port 1883.
