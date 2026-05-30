// Main application logic, extracted from Arduino setup() so integration tests
// can call run_app() directly without the Arduino runtime.
//
// IMPORTANT: every call to sleep() / sleep_for() is followed by an explicit
// return. On-device those calls never return (esp_deep_sleep_start() is
// terminal); the return is unreachable in production but allows test stubs to
// return normally so post-sleep state can be inspected.

#include <Arduino.h>
#include <ezTime.h>
#include <SPIFFS.h>
#include <WiFi.h>

#include "IBoard.h"
#include "app.h"
#include "backoff.h"
#include "battery.h"
#include "defaults.h"
#include "display_utils.h"
#include "error_utils.h"
#include "log_utils.h"
#include "network_utils.h"
#include "version.h"
#include "sleep_utils.h"
#include "time_utils.h"

#if defined(USE_SDCARD)
#include <ArduinoJson.h>
#include <ArduinoYaml.h>
#include "InkplateBoard.h"
#include "file_utils.h"
#endif

// Provided by main.cpp (firmware) or test_main.cpp (tests).
extern IBoard& board;

// RTC_DATA_ATTR marks variables that survive deep-sleep cycles on ESP32.
// On the host (NATIVE) they are plain globals.
RTC_DATA_ATTR int bootCount = 0;
// Seconds-until-next-refresh as dictated by the server's
// X-Next-Refresh-Seconds header. Zero-init on cold boot; preserved across
// deep-sleep cycles. When 0, falls back to serverDefaultRefreshSeconds.
RTC_DATA_ATTR uint32_t nextRefreshSeconds;
// Exponential back-off step. Incremented on each failed boot (download or
// draw). Reset to 0 on full success. Zero-init on cold reset.
RTC_DATA_ATTR int serverBackoffStep;
// Next URL to fetch as directed by the server's X-Next-URL header.
// Empty string on cold boot → falls back to serverURL from config.
RTC_DATA_ATTR char nextServerURL[256];

#ifdef NATIVE
void reset_app_state() {
    bootCount = 0;
    nextRefreshSeconds = 0;
    serverBackoffStep = 0;
    nextServerURL[0] = '\0';
}
#endif

void run_app() {
    ++bootCount;

    Serial.begin(115200);
    // Init inkplate board.
    board.begin();
    // Init SPIFFS for calendar image cache (preserves calendar behind banners).
    if (!SPIFFS.begin(true)) {
        log(LOG_WARNING, "SPIFFS mount failed - calendar cache unavailable");
    }
    // Set board to portrait mode.
    board.setRotation(1);
    // Set clock from RTC.
    board.rtcGetData();
    time_t bootTime = board.rtcGetEpoch();
    setTime(bootTime);

    logf(LOG_NOTICE, "##### %s Weather Calendar boot #%d #####", board.deviceName(), bootCount);
    logf(LOG_NOTICE, "############ Client version: %s ############", CLIENT_VERSION);
    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    switch (wakeup_reason) {
        case ESP_SLEEP_WAKEUP_EXT0:
            logf(LOG_DEBUG, "wakeup caused by external signal using RTC_IO.");
            board.rtcClearAlarmFlag();
            break;
        case ESP_SLEEP_WAKEUP_EXT1:
            logf(LOG_DEBUG, "wakeup caused by external signal using RTC_CNTL.");
            break;
        case ESP_SLEEP_WAKEUP_TIMER:
            logf(LOG_DEBUG, "wakeup caused by timer.");
            break;
        case ESP_SLEEP_WAKEUP_TOUCHPAD:
            logf(LOG_DEBUG, "wakeup caused by touchpad.");
            break;
        case ESP_SLEEP_WAKEUP_ULP:
            logf(LOG_DEBUG, "wakeup caused by ULP program.");
            break;
        default:
            log(LOG_DEBUG, "wakeup caused by RST pin or power button");
            break;
    }

    // Read battery voltage.
    double bvolt = board.readBattery();
    logf(LOG_INFO, "battery voltage: %sv", String(bvolt, 2).c_str());
    // Get the battery percentage remaining.
    int batteryRemainingPercent = getBatteryCapacity(bvolt);
    logf(LOG_INFO, "approx battery capacity: %d%%", batteryRemainingPercent);

#if defined(USE_SDCARD)
    // Init storage.
    if (!board.sdCardInit()) {
        const char* errMsg = "SD card init failure";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(board.rtcGetEpoch() + SECONDS_IN_DAY);
        return; // sleep() is terminal on-device; return lets tests inspect state
    }
#endif

    if (batteryRemainingPercent <= 5) {
        log(LOG_NOTICE, "battery critical! - sleeping until charged");
        displayMessage("Battery critical, please charge!",
                       batteryRemainingPercent);
        // Sleep instead of proceeding when battery is too low.
        sleep(board.rtcGetEpoch() + SECONDS_IN_YEAR);
        return; // terminal
    } else if (batteryRemainingPercent <= 10) {
        log(LOG_WARNING, "battery low, charge soon!");
    }

    // Runtime config defaults to compile-time values and may be overridden
    // by SD config when USE_SDCARD is enabled.
    const char* activeServerURL = serverURL;
    int activeServerRetries = serverRetries;
    uint32_t activeServerDefaultRefreshSeconds = serverDefaultRefreshSeconds;

    const char* activeWifiSSID = wifiSSID;
    const char* activeWifiPass = wifiPass;
    int activeWifiRetries = wifiRetries;

    const char* activeNtpHost = ntpHost;
    const char* activeNtpTimezone = ntpTimezone;

    bool activeMqttLoggerEnabled = mqttLoggerEnabled;
    const char* activeMqttLoggerBroker = mqttLoggerBroker;
    int activeMqttLoggerPort = mqttLoggerPort;
    const char* activeMqttLoggerClientID = mqttLoggerClientID;
    const char* activeMqttLoggerTopic = mqttLoggerTopic;
    int activeMqttLoggerRetries = mqttLoggerRetries;

    // Init err state.
    esp_err_t err = ESP_OK;

#if defined(USE_SDCARD)
    SdFat &sd = static_cast<InkplateBoard&>(board).getSdFat();

    // Attempt to get config yaml file.
    FsFile file = sd.open(CONFIG_FILE_PATH, O_RDONLY);
    if (!file) {
        const char* errMsg = "Failed to open config file";
        logf(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep_for(activeServerDefaultRefreshSeconds);
        return;
    }

    // Attempt to parse yaml file.
    StaticJsonDocument<768> doc;
    DeserializationError dse = deserializeYml(doc, file);
    if (dse) {
        const char* errMsg = "Failed to load config from file";
        logf(LOG_ERROR, "failed to deserialize YAML: %s", dse.c_str());
        displayMessage(errMsg, batteryRemainingPercent);
        sleep_for(activeServerDefaultRefreshSeconds);
        return;
    }
    file.close();

    // Validate required fields before applying SD overrides.
    JsonObject serverCfg = doc["server"];
    JsonObject wifiCfg = doc["wifi"];
    JsonObject ntpCfg = doc["ntp"];

    const char* cfgServerURL = serverCfg["url"];
    const char* cfgWifiSSID = wifiCfg["ssid"];
    const char* cfgWifiPass = wifiCfg["pass"];
    const char* cfgNtpHost = ntpCfg["host"];
    const char* cfgNtpTimezone = ntpCfg["timezone"];

    if (!cfgServerURL || !cfgWifiSSID || !cfgWifiPass ||
        !cfgNtpHost || !cfgNtpTimezone) {
        const char* errMsg = "Missing required config keys";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep_for(activeServerDefaultRefreshSeconds);
        return;
    }

    // Persist SD-provided strings for the lifetime of run_app().
    static String sdServerURL;
    static String sdWifiSSID;
    static String sdWifiPass;
    static String sdNtpHost;
    static String sdNtpTimezone;
    static String sdMqttLoggerBroker;
    static String sdMqttLoggerClientID;
    static String sdMqttLoggerTopic;

    sdServerURL = cfgServerURL;
    sdWifiSSID = cfgWifiSSID;
    sdWifiPass = cfgWifiPass;
    sdNtpHost = cfgNtpHost;
    sdNtpTimezone = cfgNtpTimezone;

    activeServerURL = sdServerURL.c_str();
    activeServerRetries = serverCfg["retries"] | activeServerRetries;
    activeServerDefaultRefreshSeconds =
        serverCfg["default_refresh_seconds"] | activeServerDefaultRefreshSeconds;

    activeWifiSSID = sdWifiSSID.c_str();
    activeWifiPass = sdWifiPass.c_str();
    activeWifiRetries = wifiCfg["retries"] | activeWifiRetries;

    activeNtpHost = sdNtpHost.c_str();
    activeNtpTimezone = sdNtpTimezone.c_str();

    // Remote logging config.
    JsonObject mqttLoggerCfg = doc["mqtt_logger"];
    activeMqttLoggerEnabled = mqttLoggerCfg["enabled"] | activeMqttLoggerEnabled;
    if (mqttLoggerCfg["broker"] && mqttLoggerCfg["clientId"] && mqttLoggerCfg["topic"]) {
        sdMqttLoggerBroker = mqttLoggerCfg["broker"].as<const char*>();
        sdMqttLoggerClientID = mqttLoggerCfg["clientId"].as<const char*>();
        sdMqttLoggerTopic = mqttLoggerCfg["topic"].as<const char*>();
        activeMqttLoggerBroker = sdMqttLoggerBroker.c_str();
        activeMqttLoggerClientID = sdMqttLoggerClientID.c_str();
        activeMqttLoggerTopic = sdMqttLoggerTopic.c_str();
    }
    activeMqttLoggerPort = mqttLoggerCfg["port"] | activeMqttLoggerPort;
    activeMqttLoggerRetries = mqttLoggerCfg["retries"] | activeMqttLoggerRetries;
#endif

    // Attempt to connect to WiFi.
    err = configureWiFi(activeWifiSSID, activeWifiPass, activeWifiRetries);
    if (err == ESP_ERR_TIMEOUT) {
        const char* errMsg = "wifi connect timeout";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(board.rtcGetEpoch() + 60);
        return; // terminal
    }

    // Attempt to synchronize clocks with network time.
    err = configureTime(activeNtpHost, activeNtpTimezone);
    if (err != ESP_OK) {
        log(LOG_WARNING, "failed to synchronize RTC with network time");
    }

    if (activeMqttLoggerEnabled) {
        // Attempt to connect to MQTT broker for remote logging.
        err = configureMQTT(activeMqttLoggerBroker, activeMqttLoggerPort,
                            activeMqttLoggerTopic, activeMqttLoggerClientID,
                            activeMqttLoggerRetries);
        if (err == ESP_ERR_TIMEOUT) {
            log(LOG_WARNING,
                "failed to connect remote logging, fallback to serial");
        }
    }

    // Reset err state.
    err = ESP_FAIL;
    const char* errMsg = nullptr;
    int attempts = 0;

    int32_t defaultLen = board.getWidth() * board.getHeight() * 8 + 100;
    uint8_t *buf = nullptr;
    do {
        logf(LOG_DEBUG, "calendar download attempt #%d", attempts + 1);

        const char* fetchURL =
            (nextServerURL[0] != '\0') ? nextServerURL : activeServerURL;
        buf = downloadFile(fetchURL, &nextRefreshSeconds, &defaultLen,
                           nextServerURL, sizeof(nextServerURL));
        if (!buf) {
            errMsg = "file download error";
            log(LOG_ERROR, errMsg);
            continue;
        }
        err = ESP_OK;

        logf(LOG_INFO, "next refresh in %u seconds",
         nextRefreshSeconds ? nextRefreshSeconds
                : activeServerDefaultRefreshSeconds);
#if defined(USE_SDCARD)
        err = writeFile(buf, defaultLen, CALENDAR_RW_PATH);
        if (err != ESP_OK) {
            errMsg = "file write error";
            log(LOG_ERROR, errMsg);
            continue;
        }
#endif
    } while (err != ESP_OK && ++attempts <= activeServerRetries);

    // Disconnect and turn off WiFi radio to save power.
    log(LOG_NOTICE, "disconnecting WiFi radio...");
    WiFi.disconnect();
    WiFi.mode(WIFI_OFF);

    // If we were not successful, back off before retrying.
    if (err != ESP_OK) {
        displayMessage(errMsg, batteryRemainingPercent);
        serverBackoffStep++;
        logf(LOG_NOTICE, "server unreachable (back-off step %d): sleeping %u s",
             serverBackoffStep, computeBackoffSeconds(serverBackoffStep));
        sleep_for(computeBackoffSeconds(serverBackoffStep));
        return; // terminal
    }

    // Reset err state.
    err = ESP_FAIL;
    attempts = 0;
    do {
        logf(LOG_DEBUG, "calendar draw attempt #%d", attempts + 1);

        board.clearDisplay();
#if defined(USE_SDCARD)
        err = loadImage(CALENDAR_RW_PATH);
#else
        err = loadImage(buf, defaultLen);
#endif
        if (err != ESP_OK) {
            errMsg = "image load error";
            log(LOG_ERROR, errMsg);
            continue;
        }

        displayBatteryStatus(batteryRemainingPercent, false);

        // Send buffer to eink display.
        board.display();
    } while (err != ESP_OK && ++attempts <= activeServerRetries);

    // Draw failure: persistent local problem (corrupt image, rendering bug).
    // Back off to conserve battery — won't self-heal without a reflash.
    if (err != ESP_OK) {
        displayMessage(errMsg, batteryRemainingPercent);
        serverBackoffStep++;
        logf(LOG_NOTICE, "draw failed (back-off step %d): sleeping %u s",
             serverBackoffStep, computeBackoffSeconds(serverBackoffStep));
        sleep_for(computeBackoffSeconds(serverBackoffStep));
        return; // terminal
    }

    // Cache the drawn image so displayMessage can overlay it as a backdrop.
    if (saveCalendarCache(buf, defaultLen)) {
        log(LOG_DEBUG, "calendar cache saved to SPIFFS");
    } else {
        log(LOG_WARNING, "failed to save calendar cache to SPIFFS");
    }

    if (nextRefreshSeconds > 0) {
        // Server told us exactly when to come back — reset back-off and sleep.
        serverBackoffStep = 0;
        sleep_for(nextRefreshSeconds);
        return; // terminal
    } else {
        // Server returned an image but no valid refresh time. Back off.
        serverBackoffStep++;
        logf(LOG_NOTICE, "no refresh schedule from server (back-off step %d): sleeping %u s",
             serverBackoffStep, computeBackoffSeconds(serverBackoffStep));
        sleep_for(computeBackoffSeconds(serverBackoffStep));
        return; // terminal
    }
}
