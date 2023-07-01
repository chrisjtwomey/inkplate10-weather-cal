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
extern char serverURL[];
// The number of times to attempt downloading or drawing the server image.
extern int serverRetries;

// Wifi config.
extern char wifiSSID[];
extern char wifiPass[];
// The number of times to attempt WiFi connection before timeout.
extern int wifiRetries;

// NTP config.
// The time server (keep as pool.ntp.org if in doubt).
extern char ntpHost[];
// The timezone you live in ("Olson" format).
extern char ntpTimezone[];

// Remote logging config.
// Set to true to send publish logs to an MQTT broker.
extern bool mqttLoggerEnabled;
// The MQTT broker to publish logs to.
extern char mqttLoggerBroker[];
// The port of the MQTT broker.
extern int mqttLoggerPort;
// The unique identifier for this project in your MQTT broker.
extern char mqttLoggerClientID[];
// The name of the MQTT topic to publish to.
extern char mqttLoggerTopic[];
// The number of times to attempt MQTT connection before timeout.
extern int mqttLoggerRetries;
#endif