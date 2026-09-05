// The settings run_app() is tested against.
//
// The project's own are in src/defaults.cpp, which is gitignored and holds
// real credentials, so the test supplies its own rather than compiling that.

#ifdef NATIVE

#include "app.h"

ClientConfig compiledDefaults() {
    ClientConfig cfg = {};

    cfg.serverURL = "http://test.local:8080/image.png";
    cfg.serverRetries = 3;
    cfg.defaultRefreshSeconds = 3600;

    cfg.wifiSSID = "test-ssid";
    cfg.wifiPass = "test-pass";
    cfg.wifiRetries = 10;

    cfg.ntpHost = "pool.ntp.org";
    cfg.ntpTimezone = "Europe/Dublin";

    cfg.mqttEnabled = false;
    cfg.mqttBroker = "localhost";
    cfg.mqttPort = 1883;
    cfg.mqttClientID = "epaper-test-client";
    cfg.mqttTopic = "mqtt/epaper-test";
    cfg.mqttRetries = 3;

    return cfg;
}

#endif // NATIVE
