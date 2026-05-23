# Inkplate 10 Weather Calendar

[![PlatformIO CI](https://github.com/chrisjtwomey/inkplate10-weather-cal/actions/workflows/build.yaml/badge.svg)](https://github.com/chrisjtwomey/inkplate10-weather-cal/actions/workflows/build.yaml)
[![Release](https://github.com/chrisjtwomey/inkplate10-weather-cal/actions/workflows/release.yaml/badge.svg)](https://github.com/chrisjtwomey/inkplate10-weather-cal/actions/workflows/release.yaml)

Display weather forecasts and a stylised map of your city on an Inkplate 10 that can last for months on a single battery. Four page layouts are available: a simplified today/tomorrow view, an hourly forecast table, and a 5-day daily summary.

<img src=https://user-images.githubusercontent.com/5797356/223708925-131d7ecc-5e95-453a-b687-427b75d959dd.jpg width=800 />

## Gallery

A few example screenshots from the Inkplate 10 Weather Calendar:

<table align="center">
  <tr>
    <td align="center"><img src="doc/assets/today_dublin.png" alt="Today - Dublin" width="350" style="margin:8px;" /><br/><sub>Today view: Current weather, map, and summary for Dublin</sub></td>
    <td align="center"><img src="doc/assets/tomorrow_stockholm.png" alt="Tomorrow - Stockholm" width="350" style="margin:8px;" /><br/><sub>Tomorrow view: Forecast for Stockholm with icon and phrase</sub></td>
  </tr>
  <tr>
    <td align="center"><img src="doc/assets/hourly_reykjavik.png" alt="Hourly - Reykjavik" width="350" style="margin:8px;" /><br/><sub>Hourly view: 9-hour forecast table for Reykjavik</sub></td>
    <td align="center"><img src="doc/assets/daily_lisbon.png" alt="Daily - Lisbon" width="350" style="margin:8px;" /><br/><sub>Daily view: 5-day summary for Lisbon with icons and highs/lows</sub></td>
  </tr>
</table>

- [Background](#background)
- [How it Works](#how-it-works)
- [Bill of Materials](#bill-of-materials)
- [Setup](#setup)
  - [Server](#server)
  - [Client (Firmware)](#client-firmware)
- [Firmware](#firmware)
  - [Building with PlatformIO](#building-with-platformio)
- [License](#license)

## Background

Back in late 2021, I came across a project called [MagInkCal](https://github.com/speedyg0nz/MagInkCal) that uses a Raspberry Pi Zero WH to retrieve events from a Google calendar and display them on an e-ink display. One of the drawbacks of the project however is power consumption and I thought of porting the project over to use the ESP32 platform instead. What resulted eventually was this project, though I decided to focus on more of a weather station aspect rather than Google calendar events.

I recommend taking a look at the author's other project [MagInkDash](https://github.com/speedyg0nz/MagInkDash) which has a similar architecture to this.

## How it Works

Both a server and client are required. The main workload is in the server which allows the client to save power by not generating the image itself.

<img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/ff903fe3-4576-41d1-92b5-3a374242759a width=800 />

### Client (Inkplate 10)
1. Wakes from deep sleep and attempts to connect to WiFi.
2. Attempts to get current network time and update real-time clock.
3. (Optional) Attempts to connect to a MQTT topic to publish logs. This allows you to see what the ESP32 is doing without needing to monitor the serial connection.
4. Downloads the PNG image the server is hosting.
5. (Optional, SD card only) Writes the downloaded PNG image to SD card.
6. Reads the PNG image and writes it to the e-ink display.
7. Returns to deep sleep for the number of seconds the server dictated via `X-Next-Refresh-Seconds`. If the server doesn't provide a value, backs off exponentially (2 min → 6 min → … → 24 h) until it does.

#### Features:
  - Ultra-low power consumption:
    - approx 24µA in deep sleep
    - approx 120mA awake
    - approx 10-20 seconds awake time daily
    - **1 - 2 years+** of battery life using a 2000mAh cell.
  - Real-time clock for precise sleep/wake times.
  - Daylight savings time (DST) handled entirely server-side — the server sends seconds-until-next-refresh so the client never needs to reason about timezones for scheduling.
  - Can publish to a MQTT topic for remote logging.
  - Renders messages on the e-ink display for critical errors (battery low, WiFi timeout, etc.). The previous calendar image stays visible behind the banner (cached in SPIFFS on first successful refresh).
  - Exponential back-off on server failures: 2 min → 6 min → 18 min → … → 24 h cap, resetting on the next successful server-dictated refresh.
  - Optional: SD card support for loading client config from `config.yaml` without reflashing (see [Setup](#client-firmware)).

#### Power Consumption

See [doc/power-consumption.md](doc/power-consumption.md) for details on power consumption and battery performance.

### Server
See [server/README.md](server/README.md) for full server documentation.

## Bill of Materials

- **Inkplate 10 by Soldered Electronics ~€150**

  The [Inkplate 10](https://www.crowdsupply.com/soldered/inkplate-10) is an all-in-one hardware solution. It has a 9.7" 1200x825 display with integrated ESP32, real-time clock, and battery power management. You can get it [directly from Soldered Electronics](https://soldered.com/product/soldered-inkplate-10-9-7-e-paper-board-with-enclosure-copy) or from a [UK reseller like Pimoroni](https://shop.pimoroni.com/products/inkplate-10-9-7-e-paper-display?variant=39959293591635).

- **Optional: 2 GB microSD card ~€5**

  **Note: SD card support is disabled by default. Use build flag `USE_SDCARD` to enable.**

  Only needed if you want to load client config (`config.yaml`) from the card without reflashing. Image caching for error banners is handled automatically via internal SPIFFS flash.

- **3000mAh LiPo battery pack ~€10**

  Any Lithium-Ion/Polymer battery with a JST connector. Some Inkplate 10s are sold with a 3000mAh battery (~6 months of life). See [doc/power-consumption.md](doc/power-consumption.md) for real-world numbers.

- **CR2032 3V coin cell ~€1**

  Powers the real-time clock during deep sleep.

- **A server to run the image generator**

  Anything that can run Docker or Python 3.10+. A Raspberry Pi Zero 2W is a good low-power option; any always-on computer works.

- **Black photo frame 8"x10" ~€10**

  The mount needs to fit an 8"x10" frame but expose only the e-ink area (~5.5"x7.5").

## Setup

### Running via Docker

See [server/README.md](server/README.md) for full details:

```sh
docker run -d --restart unless-stopped \
  -p 8080:8080 \
  -e WEATHER_SERVICE=accuweather \
  -e WEATHER_APIKEY=<your_key> \
  -e GOOGLE_APIKEY=<your_key> \
  -e GOOGLE_STATICMAPS_MAPID=<your_map_id> \
  -e LOCATION="Cork" \
  -e SERVER_TIMEZONE="Europe/Dublin" \
  ghcr.io/chrisjtwomey/inkplate10-weather-cal-server:latest
```

To build from source instead (e.g. after local changes):

```sh
docker build -t weather-cal-server ./server
docker run -d --restart unless-stopped -p 8080:8080 \
  -e SERVER_TIMEZONE="Europe/Dublin" \
  ... \
  weather-cal-server
```

`SERVER_TIMEZONE` controls when the daily refresh times fire. Any config key from `server/config.example.yaml` can be overridden via env var — see [server/README.md](server/README.md) for the full mapping table.

The server regenerates the calendar image at startup and then at each time in `server.refresh_times` (default 09:00, 15:00, 21:00). The response to `GET /calendar.png` includes an `X-Next-Refresh-Seconds` header telling the client exactly how long to sleep — DST and timezone handling stay entirely server-side.

### Running locally

The server uses Selenium + Chrome to render the HTML template into a PNG. In Docker, Chromium is installed automatically. When running locally, you may need to point `CHROME_BIN` at your browser:

#### macOS 

`/usr/bin/chromium` doesn't exist, so `CHROME_BIN` is required:

```sh
export CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# or, if using Chromium via Homebrew:
# export CHROME_BIN="/Applications/Chromium.app/Contents/MacOS/Chromium"
```
If Chrome isn't installed: `brew install --cask google-chrome`

#### Linux 

Works out of the box if Chromium is at `/usr/bin/chromium` (the default):

```sh
sudo apt install chromium chromium-driver   # Debian/Ubuntu
```
If using Google Chrome instead:
```sh
export CHROME_BIN="/usr/bin/google-chrome"
```

#### Windows

`/usr/bin/chromium` doesn't exist, so `CHROME_BIN` is required:

```powershell
$env:CHROME_BIN = "C:\Program Files\Google\Chrome\Application\chrome.exe"
```

> **Note:** Selenium Manager may emit warnings about `chromedriver` version mismatches or `/usr/bin/chromium` not existing. These are harmless — set `CHROME_BIN` as above and they will go away.

#### Run once (template development)

Regenerates the calendar PNG and exits — no HTTP server, no scheduler:

```sh
cd server && python3 server.py --once
# Output: server/views/calendar.png
```

#### Run as a daemon

Starts the full HTTP server and regeneration scheduler:

```sh
cd server && python3 server.py
```

The server listens on the port configured in `config.yaml` (default `8080`) and serves the calendar image at `GET /calendar.png`.

### Client (Firmware)

The client is configured either via a header file compiled into the firmware (Option 1, no SD card needed) or via a YAML file on an SD card (Option 2).

#### Option 1: `src/defaults.cpp` _(recommended — no SD card required)_

**Note: The older E-Radionica Inkplate 10 is [missing hardware](https://github.com/SolderedElectronics/Inkplate-Arduino-library/issues/209#issuecomment-1608843488) to control power to the SD card module, causing up to 2 mA drain during deep sleep. Use this option to preserve battery life.**

Copy the example file and fill in your values:

```sh
cp src/defaults.example.cpp src/defaults.cpp
```

`src/defaults.cpp` is gitignored so your credentials stay local. Edit the key fields:

```cpp
// Server URL — hostname or IP of the machine running the server
// Use today.png, tomorrow.png, hourly.png, or daily.png (see server/README.md)
char serverURL[] = "http://YOUR_SERVER_HOST:8080/today.png";

// WiFi credentials
char wifiSSID[] = "your_wifi_ssid";
char wifiPass[] = "your_wifi_password";

// Timezone (Olson format) — used for log message timestamps only.
// Wake scheduling is dictated by the server via X-Next-Refresh-Seconds/
char ntpTimezone[] = "Europe/Dublin";

// Optional: MQTT remote logging
bool mqttLoggerEnabled = true;
char mqttLoggerBroker[] = "YOUR_SERVER_HOST";
```

#### Option 2: SD card YAML _(for SolderedElectronics Inkplate 10 with SD card)_

**Note: Use build flag `USE_SDCARD` to enable SD card support.**

Place a `config.yaml` in the root of your SD card:

```yaml
server:
  # Use today.png, tomorrow.png, hourly.png, or daily.png (see server/README.md)
  url: http://YOUR_SERVER_HOST:8080/today.png
  retries: 3
wifi:
  ssid: XXXX
  pass: XXXX
  retries: 6
ntp:
  host: pool.ntp.org
  timezone: Europe/Dublin
mqtt_logger:
  enabled: false
  broker: localhost
  port: 1883
  clientId: inkplate10-weather-calendar
  topic: mqtt/inkplate10-weather-calendar
  retries: 3
```

See [doc/config.yaml](doc/config.yaml) for a fully annotated example.

## Firmware

### Flashing a pre-built binary

Each [GitHub release](https://github.com/chrisjtwomey/inkplate10-weather-cal/releases) includes a pre-built `firmware.bin`. Flash it directly without installing PlatformIO:

```sh
pip install esptool
esptool.py --chip esp32 --port /dev/ttyUSB0 write_flash 0x10000 firmware.bin
```

### Building with PlatformIO

Clone the repo, copy your config as above, then build and flash:

```sh
pio run -e debug -t upload
```

`platformio.ini` has two environments:

| Environment | Use |
|---|---|
| `debug` | Verbose serial logging (`LOG_LEVEL=5`). Use during development. |
| `release` | Minimal logging (`LOG_LEVEL=4`). Use for day-to-day deployment. |

### Running the tests

A suite of native (host-side) unit tests covers pure logic — back-off timing, battery capacity, refresh header parsing, scheduling — no device needed:

```sh
pio test -e native
```

## License

All code in this repository is licensed under the MIT license.

Weather icons by [lutfix](https://www.flaticon.com/authors/lutfix) from [www.flaticon.com](https://www.flaticon.com).
