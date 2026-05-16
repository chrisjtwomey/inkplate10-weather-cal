#ifndef __DEFAULTS_H__
#define __DEFAULTS_H__
#include <stdint.h>
/**
 * Manually define config params.
 *
 * Only use this if you are not using the SD card (Inkplate10 V1).
 * Otherwise add USE_SDCARD flag to load from SD card config.yaml
 *
 * These parameters are overriden by the config.yaml if SD card is enabled.
 *
 * To use: copy this file to src/defaults.cpp and fill in your real values.
 * src/defaults.cpp is gitignored so your credentials stay local.
 */

// The URL on the server which the client will try to download from.
char serverURL[] = "http://YOUR_SERVER_HOST:8080/calendar.png";
// The number of times to attempt downloading or drawing the server image.
int serverRetries = 3;
// Fallback seconds-until-next-refresh when the server hasn't dictated one
// yet (cold boot, or server unreachable). 3600 = 1 hour retry.
uint32_t serverDefaultRefreshSeconds = 3600;

// Wifi config.
char wifiSSID[] = "XXXX";
char wifiPass[] = "XXXX";
// The number of times to attempt WiFi connection before timeout.
int wifiRetries = 10;

// NTP config.
// The time server (keep as pool.ntp.org if in doubt).
char ntpHost[] = "pool.ntp.org";
// The timezone you live in ("Olson" format), e.g. Europe/Dublin.
char ntpTimezone[] = "Europe/Dublin";

// Remote logging config.
// Set to true to send publish logs to an MQTT broker.
bool mqttLoggerEnabled = false;
// The MQTT broker to publish logs to.
char mqttLoggerBroker[] = "localhost";
// The port of the MQTT broker.
int mqttLoggerPort = 1883;
// The unique identifier for this project in your MQTT broker.
char mqttLoggerClientID[] = "inkplate10-weather-client";
// The name of the MQTT topic to publish to.
char mqttLoggerTopic[] = "mqtt/eink-cal-client";
// The number of times to attempt MQTT connection before timeout.
int mqttLoggerRetries = 3;
#endif
