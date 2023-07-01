# Inkplate 10 Weather Calendar

Display today's date, weather forecast and a stylised map of your city using an Inkplate 10 that can last for months on a single battery.

<img src=https://user-images.githubusercontent.com/5797356/223708925-131d7ecc-5e95-453a-b687-427b75d959dd.jpg width=800 />

- [Background](#background)
- [How it Works](#how-it-works)
- [Bill of Materials](#bill-of-materials)
- [Setup](#setup)
- [Firmware](#firmware)
  - [Building with PlatformIO](#building-with-platformio)
- [License](#license)

## Background

Back in late 2021, I came across a project called [MagInkCal](https://github.com/speedyg0nz/MagInkCal) that uses a Raspberry Pi Zero WH to retrieve events from a Google calendar and display them on an e-ink display. One of the drawbacks of the project however is power consumption and I thought of porting the project over to use the ESP32 platform instead. What resulted eventually was this project, though I decided to focus on more of a weather station aspect rather than Google calendar events.

I recommend taking a look at the author's other project [MagInkDash](https://github.com/speedyg0nz/MagInkDash) which has a similar architecture to this.

## How it Works

Both a server and client and required. The main workload is in the server which allows the client to save power by not generating the image itself. The client can also be placed where it has access to your WiFi network.

<img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/ff903fe3-4576-41d1-92b5-3a374242759a width=800 />

### Client (Inkplate 10)
1. Wakes from deep sleep and attempts to connect to WiFi.
2. Attempts to get current network time and update real-time clock.
3. (Optional) Attempts to connect a MQTT topic to publish logs. This allows us to see what the ESP32 controller is doing without needing to monitor the serial connection.
4. Attempt to download the PNG image that the server is hosting.
5. (Optional) Write the downloaded PNG image to SD card.
6. Read the PNG image back from SD card and write to the e-ink display.
7. Returns to deep sleep until the next scheduled wake time (eg. 24 hours).

#### Features:
  - Ultra-low power consumption:
    - approx 24µA in deep sleep
    - approx 120mA awake
    - approx 10-20 seconds awake time daily
    - **1 - 2 years+** of battery life using a 2000mAh cell.
  - Real-time clock for precise sleep/wake times.
  - Daylight savings time handled automatically.
  - Can publish to a MQTT topic for remote-logging.
  - Renders messages on the e-ink display for critical errors (eg. battery low, wifi connect timeout etc.).
  - Optional: stores calendar images on SD card.
  - Optional: reconfigure client by updating YAML file on SD card and reboot - easy!

#### Power Consumption

See [doc/power-consumption.md](doc/power-consumption.md) for details on power consumption and battery performance.

#### Features:
See the [server/README.md](server/README.md) for more features.


## Bill of Materials

- **Inkplate 10 by Soldered Electronics ~€150**

  The [Inkplate 10](https://www.crowdsupply.com/soldered/inkplate-10) is an all-in-one hardware solution for something like this. It has a 9.7" 1200x825 display with integrated ESP32, real-time clock, and battery power management. You can get it either [directly from Soldered Electronics](https://soldered.com/product/soldered-inkplate-10-9-7-e-paper-board-with-enclosure-copy) or from a [UK reseller like Pimoroni](https://shop.pimoroni.com/products/inkplate-10-9-7-e-paper-display?variant=39959293591635). While it might seem pricey at first glance, a [similarly sized raw display from Waveshare](https://www.amazon.co.uk/Waveshare-Parallel-Resolution-Industrial-Instrument/dp/B07JG4SXBV) can cost the same or likely more, and you would still need to source the microcontroller, RTC, and BMS yourself.

  If you want to use a more generic e-ink display or you just want to do a DIY build, there is a [branch](https://github.com/chrisjtwomey/inkplate10-weather-cal/tree/gxepd2) that's designed to work with GXEPD2, but it's likely missing fixes and features from the main branch.
  
- **Optional: 2 GB microSD card ~€5**

  **Note: microSD cards are now no longer required and disabled by default. Use build flag `USE_SDCARD` to re-enable**
  
  Whatever is the cheapest microSD card you can find, you will not likely need more than few hundred kilobytes of storage. It will be mainly used by Inkplate to cache downloaded images from the server until it needs to refresh the next day. The config file for the code will also need to be stored here.

- **3000mAh LiPo battery pack ~€10**

  Any Lithium-Ion/Polymer battery will do as long as they have a JST connector for hooking up to the Inkplate board. Some Inkplate 10's are sold with a 3000mAh battery which should give approximately 6 months of life. Here is [the battery I used](https://cdn-shop.adafruit.com/datasheets/LiIon2000mAh37V.pdf). See section on [power consumption](doc/power-consumption.md) for more info on real-world calculations.

- **CR2032 3V coin cell ~€1**

  In order to power the real-time clock for when the board needs to deep sleep. Should be easily-obtainable in any hardware or home store.
  
- **Raspberry Pi Zero W ~€40**

  To run the server, you will need to something that can run Python 3 and chromedriver. The server itself is lightweight with the only real work involved is chromedriver generating a PNG image before serving it to the client. It can also be configured to auto-shutdown when it has successfully served the image to the client. A board such as the Raspberry Pi Zero W is perfect for its low power-consumption but any computer you're happy with running 24/7 is suitable.
  
- **Black photo frame 8"x10" ~€10**

  This might be the trickiest part to source, as the card insert (also called the 'mount') needs to fit the 8"x10" frame but fit a photo closer in dimension to 5.5"x7.5" in order for just the e-ink part of the board to be in-frame.

## Setup

### Option #1: using config header file _(recommended for E-Radionica Inkplate10)_

**Note: The old _E-Radionica_ version of Inkplate10 is missing hardware to control power to the SD card module which results in up to 2mA power consumption during deep sleep, therefore it's recommended you use this option to preserve battery life. See https://github.com/SolderedElectronics/Inkplate-Arduino-library/issues/209.**

Update `config.h` with the:
```
// Assign config values.
const char* calendarUrl = "http://localhost:8080/calendar.png";
const char* calendarDailyRefreshTime = "09:00:00";
const int calendarRetries = 3;  // number of times to retry draw/download

// Wifi config.
const char* wifiSSID = "XXXX";
const char* wifiPass = "XXXX";
const int wifiRetries = 6;  // number of times to retry WiFi connection

// NTP config.
const char* ntpHost =
    "pool.ntp.org";  // the time server host (keep as pool.ntp.org if in doubt)
const char* ntpTimezone = "Europe/Dublin";

// Remote logging config.
bool mqttLoggerEnabled =
    false;  // set to true for remote logging to a MQTT broker
const char* mqttLoggerBroker = "localhost";  // the broker host
const int mqttLoggerPort = 1883;
const char* mqttLoggerClientID = "inkplate10-weather-client";
const char* mqttLoggerTopic = "mqtt/inkplate10-weather-client";
const int mqttLoggerRetries = 3;  // number of times to retry MQTT connection
```

Make sure to update: 
- `wifiSSID` - the SSID if your WiFi network.
- `wifiPass` - the WiFi password.
- `calendarUrl` - the hostname or IP address of your server which the client will attempt to download the image from.
- `calendarDailyRefreshTime` - the time you want the client to wake each day, in `HH:MM:SS` format.
- `ntpTimezone` - the timezone you live in (in "Olson" format), otherwise the client might not wake at the expected time.  
- `mqttLoggerBroker` - the hostname or IP address of your server (likely the same server as the image host).


### Option #2: Using a microSD card _(recommended for SolderedElectronics Inkplate10)_

**Note: The new/current _SolderedElectronics_ version of Inkplate10 has a MOSFET to control power to the SD card during deep sleep, making this option viable for battery life. https://github.com/SolderedElectronics/Inkplate-Arduino-library/issues/209**

**Note: Use build flag `USE_SDCARD` to enable SD card usage.**

Insert an SD card into your Inkplate board and place a new file `config.yaml` in the root directory:

```
calendar:
  url: http://localhost:8080/calendar.png
  daily_refresh_time: 09:00:00
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
  clientId: inkplate10-weather-cal
  topic: mqtt/weather-cal
  retries: 3
```

Make sure to update: 
- `wifi.ssid` - the SSID if your WiFi network.
- `wifi.pass` - the WiFi password.
- `calendar.url` - the hostname or IP address of your server which the client will attempt to download the image from.
- `calendar.daily_refresh_time` - the time you want the client to wake each day, in `HH:MM:SS` format.
- `ntp.timezone` - the timezone you live in (in "Olson" format), otherwise the client might not wake at the expected time.  
- `mqtt_logger.broker` - the hostname or IP address of your server (likely the same server as the image host).

See the [server/README.md](server/README.md) for info on server setup.

## Firmware

### Building with PlatformIO

Should be as simple as cloning the project from GitHub and importing into PlatformIO. `platformio.ini` has everything setup to build and upload to Inkplate 10.

## License

All code in this repository is licensed under the MIT license.

Weather icons by [lutfix](https://www.flaticon.com/authors/lutfix) from [www.flaticon.com](https://www.flaticon.com).
