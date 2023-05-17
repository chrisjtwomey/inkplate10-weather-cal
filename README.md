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

If you are looking for a solution for Raspberry Pi, I recommend taking a look at the author's other project [MagInkDash](https://github.com/speedyg0nz/MagInkDash).

## How it Works

Both a server and client and required. The main workload is in the server will allows the client to save power by not generating the image itself. 

<img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/ff903fe3-4576-41d1-92b5-3a374242759a width=800 />

### Client (Inkplate 10)
1. Wakes from deep sleep and attempts to connect to WiFi.
2. Attempts to get current network time and update real-time clock.
3. (Optional) Attempts to connect a MQTT topic to publish logs. This allows us to see what the ESP32 controller is doing without needing to monitor the serial connection.
4. Attempt to download the PNG image that the server is hosting.
5. Write the downloaded PNG image to SD card.
6. Read the PNG image back from SD card and write to the e-ink display.
7. Returns to deep sleep until the next scheduled wake time (eg. 24 hours).

#### Features:
  - Ultra-low power consumption:
    - approx 21µA in deep sleep
    - approx 240mA awake
    - approx 30 seconds awake time daily
  - Real-time clock for precise sleep/wake times.
  - Daylight savings time handled automatically.
  - Can publish to a MQTT topic for remote-logging.
  - Renders messages on the e-ink display for critical errors (eg. battery low, wifi connect timeout etc.).
  - Stores calendar images on SD card.
  - Reconfigure client by updating YAML file on SD card and reboot - easy!

#### Power Consumption

With a 2000mAh LiPo battery, the client could theoretically go 4 to 5 months without a recharge, possibly 6 months with a 3000mAh pack. The client takes a reading of the battery voltage on every boot and will try to publish it to the server logs (if MQTT is enabled). With this, we can plot the current voltage against a typical voltage curve for a 3.7v LiPo battery:

<img src=https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/cc1db265-2312-449d-a8c4-9a53bed72a8e width=800 />

I will try to update this graph every few weeks as more voltage readings are taken and projected battery life becomes more accurate. 

The current performance is poorer than expected, however the battery is a couple years old and has gone through a decent number of charge/discharge cycles; it's likely a newer cell would perform better. It's also possible the microcontroller is using more power than expected under deep sleep.

### Server (Raspberry Pi)
1. Gets any relevant new data (ie. weather, maps).
2. Generates a HTML file using a Python HTML translator [Airium](https://pypi.org/project/airium/).
3. [Chromedriver](https://chromedriver.chromium.org/downloads) is then used to turn that generated HTML file into PNG image that fits the dimensions of e-ink resolution.
4. A [Flask](https://flask.palletsprojects.com/en/2.3.x/) server is then started to serve the generated PNG image to the client.
5. (Optional) The server listens for client logs by subscribing to a MQTT topic using [Mosquitto](https://mosquitto.org/).
6. Depending on configuration the server will either shutdown, run indefinitely, or shutdown after a certain number of times the image is served.
7. A cronjob ensures the server is started at the next scheduled wake time of the client.

#### Features:
See the [server](/server) for more features.


## Bill of Materials

- **Inkplate 10 by Soldered Electronics ~€150**

  The [Inkplate 10](https://www.crowdsupply.com/soldered/inkplate-10) is an all-in-one hardware solution for something like this. It has a 9.7" 1200x825 display with integrated ESP32, real-time clock, and battery power management. You can get it either [directly from Soldered Electronics](https://soldered.com/product/soldered-inkplate-10-9-7-e-paper-board-with-enclosure-copy) or from a [UK reseller like Pimoroni](https://shop.pimoroni.com/products/inkplate-10-9-7-e-paper-display?variant=39959293591635). While it might seem pricey at first glance, a [similarly sized raw display from Waveshare](https://www.amazon.co.uk/Waveshare-Parallel-Resolution-Industrial-Instrument/dp/B07JG4SXBV) can cost the same or likely more, and you would still need to source the microcontroller, RTC, and BMS yourself.

  If you want to use a more generic e-ink display or you just want to do a DIY build, there is a [branch](https://github.com/chrisjtwomey/inkplate10-weather-cal/tree/gxepd2) that's designed to work with GXEPD2, but it's likely missing fixes and features from the main branch.
  
- **2 GB microSD card ~€5**
  
  Whatever is the cheapest microSD card you can find, you will not likely need more than few hundred kilobytes of storage. It will be mainly used by Inkplate to cache downloaded images from the server until it needs to refresh the next day. The config file for the code will also need to be stored here.

- **3000mAh LiPo battery pack ~€10**

  Any Lithium-Ion/Polymer battery will do as long as they have a JST connector for hooking up to the Inkplate board. Some Inkplate 10's are sold with a 3000mAh battery which should give approximately 6 months of life. Here is [the battery I used](https://cdn-shop.adafruit.com/datasheets/LiIon2000mAh37V.pdf). See section on [power consumption](#power-consumption) for more info on real-world calculations.

- **CR2032 3V coin cell ~€1**

  In order to power the real-time clock for when the board needs to deep sleep. Should be easily-obtainable in any hardware or home store.
  
- **Raspberry Pi Zero W ~€40**

  To run the server, you will need to something that can run Python 3 and chromedriver. The server itself is lightweight with the only real work involved is chromedriver generating a PNG image before serving it to the client. It can also be configured to auto-shutdown when it has successfully served the image to the client. A board such as the Raspberry Pi Zero W is perfect for its low power-consumption but any computer you're happy with running 24/7 is suitable.
  
- **Black photo frame 8"x10" ~€10**

  This might be the trickiest part to source, as the card insert (also called the 'mount') needs to fit the 8"x10" frame but fit a photo closer in dimension to 5.5"x7.5" in order for just the e-ink part of the board to be in-frame.

## Setup

Place `config.yaml` in the root directory of an SD card and connect it to your Inkplate 10 board.

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

Likely parameters you'll need to change is 
- `wifi.ssid` - the SSID if your WiFi network.
- `wifi.pass` - the WiFi password.
- `calendar.url` - the hostname or IP address of your server which the client will attempt to download the image from.
- `calendar.daily_refresh_time` - the time you want the client to wake each day, in `HH:MM:SS` format.
- `ntp.timezone` - the timezone you live in (in "Olson" format), otherwise the client might not wake at the expected time.  
- `mqtt_logger.broker` - the hostname or IP address of your server (likely the same server as the image host).

See the [server](/server) for info on server setup.

## Firmware

### Building with PlatformIO

Should be as simple as cloning the project from GitHub and importing into PlatformIO. `platformio.ini` has everything setup to build and upload to Inkplate 10.

## License

All code in this repository is licensed under the MIT license.

Weather icons by [lutfix](https://www.flaticon.com/authors/lutfix) from [www.flaticon.com](https://www.flaticon.com).
