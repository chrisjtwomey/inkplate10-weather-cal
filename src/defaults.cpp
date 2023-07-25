#ifndef __DEFAULTS_H__
#define __DEFAULTS_H__
/**
 * Manually define config params.
 *
 * Only use this if you are not using the SD card (Inkplate10 V1).
 * Otherwise add USE_SDCARD flag to load from SD card config.yaml
 *
 * These parameters are overriden by the config.yaml if SD card is enabled.
 */

// The URL on the server which the client will try to download the first
// image from.
char serverURL[] = "http://localhost:8080/download.png";
// The number of times to attempt downloading or drawing the server image.
int serverRetries = 3;
// Fallback time to refresh.
char serverDefaultRefreshTime[9] = "08:45:00";

// Wifi config.
char wifiSSID[] = "XXXX";
char wifiPass[] = "XXXX";
// The number of times to attempt WiFi connection before timeout.
int wifiRetries = 6;

// NTP config.
// The time server (keep as pool.ntp.org if in doubt).
char ntpHost[] = "pool.ntp.org";
// The timezone you live in ("Olson" format).
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
char mqttLoggerTopic[] = "mqtt/inkplate10-weather-client";
// The number of times to attempt MQTT connection before timeout.
int mqttLoggerRetries = 3;
#endif