#ifndef CONFIG_H
#define CONFIG_H

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

#endif