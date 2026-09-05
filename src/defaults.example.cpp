/**
 * The settings this image is built with.
 *
 * Copy this file to src/defaults.cpp and fill in your own values.
 * src/defaults.cpp is gitignored, so your credentials stay local.
 *
 * Three of these are also kept on the board itself, and a real value here is
 * written there as it passes: the server URL, the WiFi credentials, and the
 * whole MQTT block. That is what lets an image built by CI — which has only
 * the placeholders below — still reach your network and your broker. So one
 * flash over USB with real values provisions the board for good.
 *
 * With USE_SDCARD, a config.yaml on the card overrides any of it.
 */
#include "settings.h"

ClientConfig compiledDefaults() {
    ClientConfig cfg = {};

    // The first page to fetch. After that the server names the next one.
    cfg.serverURL = "http://YOUR_SERVER_HOST:8080/today.png";
    // How many further attempts at downloading or drawing a page.
    cfg.serverRetries = 3;
    // How long to sleep when the server has not said — a cold boot, or every
    // attempt failed. 3600 = retry in an hour.
    cfg.defaultRefreshSeconds = 3600;

    cfg.wifiSSID = "XXXX";
    cfg.wifiPass = "XXXX";
    // How many attempts before giving up on WiFi for this wake.
    cfg.wifiRetries = 10;

    // The time server (keep as pool.ntp.org if in doubt) and your timezone
    // in "Olson" format, e.g. Europe/Dublin.
    cfg.ntpHost = "pool.ntp.org";
    cfg.ntpTimezone = "Europe/Dublin";

    // Remote logging. Leave the broker as XXXX and the whole block comes from
    // the board's own store instead, which is what a CI image relies on.
    cfg.mqttEnabled = false;
    cfg.mqttBroker = "XXXX";
    cfg.mqttPort = 1883;
    cfg.mqttClientID = "inkplate10-weather-client";
    cfg.mqttTopic = "mqtt/eink-cal-client";
    // How many attempts before giving up on the broker.
    cfg.mqttRetries = 3;

    return cfg;
}
