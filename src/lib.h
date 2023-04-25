#ifndef LIB_H
#define LIB_H
#include <Inkplate.h>
#include <NTPClient.h>
#include <TimeLib.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/rtc_io.h>
#include <esp_adc_cal.h>
#include <rom/rtc.h>
#include <time.h>

#include "MqttLogger.h"

// The number of seconds to sleep if RTC not configured correctly.
#define DEEP_SLEEP_FALLBACK_SECONDS 120
// set the log verbosity
#define LOG_LEVEL LOG_DEBUG
// The file path on SD card to load config.
#define CONFIG_FILE_PATH "/config.yaml"
// Fallback time to refresh.
#define CONFIG_DEFAULT_CALENDAR_DAILY_REFRESH_TIME "09:00:00"
// The path on SD card where calendar images are downloaded to and read from.
#define CALENDAR_RW_PATH "/calendar.png"
// Guestimate file size for PNG image @ 1200x825
#define CALENDAR_IMAGE_SIZE E_INK_WIDTH* E_INK_HEIGHT * 4 + 100

// Enum of errors that might be encountered.
#define ESP_ERR_ERRNO_BASE (0)
#define ESP_ERR_EDL (1 + ESP_ERR_ERRNO_BASE)     // Download error
#define ESP_ERR_EDRAW (2 + ESP_ERR_ERRNO_BASE)   // Draw error
#define ESP_ERR_EFILEW (3 + ESP_ERR_ERRNO_BASE)  // File write error
#define ESP_ERR_ENTP (4 + ESP_ERR_ERRNO_BASE)    // NTP error

// Enum of log verbosity levels.
#define LOG_CRIT 0
#define LOG_ERROR 1
#define LOG_WARNING 2
#define LOG_NOTICE 3
#define LOG_INFO 4
#define LOG_DEBUG 5

#ifndef LOG_LEVEL
// Debug logging by default.
#define LOG_LEVEL LOG_DEBUG
#endif

// The number of times we have booted (from off or from sleep).
extern RTC_DATA_ATTR int bootCount;
// RTC epoch of the last time we booted.
extern RTC_DATA_ATTR time_t lastBootTime;
// RTC epoch of the last time deep sleep was initiated.
extern RTC_DATA_ATTR time_t lastSleepTime;
// RTC epoch of the time in the future when we want to end deep sleep.
extern RTC_DATA_ATTR time_t targetWakeTime;
// The number of seconds between RTC epoch and NTP epoch.
extern RTC_DATA_ATTR unsigned long driftSecs;
// The remote logging instance.
extern MqttLogger mqttLogger;
// The Inkplate board driver instance.
extern Inkplate board;

/**
  Connect to a WiFi network in Station Mode.

  @param ssid the network SSID.
  @param pass the network password.
  @param retries the number of connection attempts to make before returning an
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
esp_err_t configureWiFi(const char* ssid, const char* pass, int retries);

/**
  Download a file at a given URL. Store the file on disk at a given path.

  @param url the URL of the file to download.
  @param size the size of the file to download.
  @param retries the number of download attempts to make before returning an
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
esp_err_t downloadFile(const char* url, int32_t size, const char* filePath);

/**
  Draw an image to the display.

  @param filePath the path of the file on disk.
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t displayImage(const char* filePath);

/**
  Draw an message to the display. The error message is drawn in the top-left
  corner of the display. Error message will overlay previously drawn image.

  @param msg the message to display.
  error.
*/
void displayMessage(const char* msg);

/**
  Connect to an NTP server and synchronize the on-board real-time clock.

  @param host the hostname of the NTP server (eg. pool.ntp.org).
  @param gmtOffset the timezone offset from GMT in hours. (eg. 0 == GMT, 1 ==
  GMT+1). error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_ENTP if updating the NTP client fails.
*/
esp_err_t configureTime(const char* host, int gmtOffset);

/**
  Get the next scheduled time to wake from deep sleep.

  @param refreshTime the time of the day to wake in HH::MM:SS format (eg.
  09:00:00). error.
  @returns the epoch time of when to wake.
  If the real-time clock is not configured, it will return the last configured
  RTC epoch time + DEEP_SLEEP_FALLBACK_SECONDS.
*/
time_t getWakeTime(const char* refreshTime);

/**
  Enter deep sleep.

  @param refreshTime the time of the day to wake in HH:MM:SS format (eg.
  09:00:00). error.
*/
void sleep(const char* refreshTime);

/**
  Format epoch time.

  @returns a representation of epoch time in the format DD:MM:YY HH:MM:SS
*/
const char* fmtTime(uint32_t t);

/**
  Connect to a MQTT broker for remote logging.

  @param broker the hostname of the MQTT broker.
  @param port the port of the MQTT broker.
  @param topic the topic to publish logs to.
  @param clientID the name of the logger client to appear as.
  @param max_retries the number of connection attempts to make before fallback
  to serial-only logging.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
esp_err_t configureMQTT(const char* broker, int port, const char* topic,
                        const char* clientID, int max_retries);

/**
  Log a message.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param msg the message to log.
*/
void log(uint16_t pri, const char* msg);

/**
  Log a message with formatting.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param fmt the format of the log message
*/
void logf(uint16_t pri, const char* fmt, ...);

/**
  Converts a priority into a log level prefix.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @returns the string value of the priority.
*/
const char* msgPrefix(uint16_t pri);

/**
  Check whether 5v USB power is detected.

  @returns a boolean whether 5v USB power is detected.
*/
bool isVbusPresent();

/**
  Gets a reading of the battery voltage by a calibrated ADC.

  @returns a float of the battery voltage.
*/
float getCalibratedBatteryVoltage();

#endif