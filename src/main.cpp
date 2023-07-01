#include <Arduino.h>
#include <Inkplate.h>
#include <ezTime.h>

#include "battery.h"
#include "defaults.h"
#include "display_utils.h"
#include "error_utils.h"
#include "log_utils.h"
#include "network_utils.h"
#include "sleep_utils.h"
#include "time_utils.h"
#if defined(USE_SDCARD)
#include "file_utils.h"
#endif

// inkplate10 board driver
Inkplate board(INKPLATE_3BIT);

void setup() {
    Serial.begin(115200);
    // Init inkplate board.
    board.begin();
    // Set board to portait mode.
    board.setRotation(1);
    // Set clock from RTC
    board.rtcGetRtcData();
    time_t bootTime = board.rtcGetEpoch();
    setTime(bootTime);

    log(LOG_NOTICE, "##### Inkplate10 Weather Calendar wake up #####");
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
    logf(LOG_INFO, "battery voltage: %sv", String(bvolt, 2));
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
    }
#endif

    if (batteryRemainingPercent <= 1) {
        log(LOG_NOTICE, "battery near empty! - sleeping until charged");
        displayMessage("Battery empty, please charge!",
                       batteryRemainingPercent);
        // Sleep instead of proceeding when battery is too low.
        sleep(board.rtcGetEpoch() + SECONDS_IN_YEAR);
    } else if (batteryRemainingPercent <= 10) {
        log(LOG_WARNING, "battery low, charge soon!");
    }

    // Init err state.
    esp_err_t err = ESP_OK;

#if defined(USE_SDCARD)
    // Attempt to get config yaml file.
    File file = sd.open(CONFIG_FILE_PATH, FILE_READ);
    if (!file) {
        const char* errMsg = "Failed to open config file";
        logf(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(FALLBACK_REFRESH_TIME);
    }

    // Attempt to parse yaml file.
    StaticJsonDocument<768> doc;
    ReadBufferingStream bufferedFile(file, 64);
    DeserializationError dse = deserializeYml(doc, bufferedFile);
    if (dse) {
        const char* errMsg = "Failed to load config from file";
        logf(LOG_ERROR, "failed to deserialize YAML: %s", dse.c_str());
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(FALLBACK_REFRESH_TIME);
    }
    file.close();

    // Assign config values.
    JsonObject serverCfg = doc["server"];
    serverURL = serverCfg["url"];
    serverRetries = serverCfg["retries"];

    // Wifi config.
    JsonObject wifiCfg = doc["wifi"];
    wifiSSID = wifiCfg["ssid"];
    wifiPass = wifiCfg["pass"];
    wifiRetries = wifiCfg["retries"];

    // NTP config.
    ntpHost = doc["ntp"]["host"];
    ntpTimezone = doc["ntp"]["timezone"];

    // Remote logging config.
    JsonObject mqttLoggerCfg = doc["mqtt_logger"];
    mqttLoggerEnabled = mqttLoggerCfg["enabled"];
    mqttLoggerBroker = mqttLoggerCfg["broker"];
    mqttLoggerPort = mqttLoggerCfg["port"];
    mqttLoggerClientID = mqttLoggerCfg["clientId"];
    mqttLoggerTopic = mqttLoggerCfg["topic"];
    mqttLoggerRetries = mqttLoggerCfg["retries"];
#endif

    // Attempt to connect to WiFi.
    err = configureWiFi(wifiSSID, wifiPass, wifiRetries);
    if (err == ESP_ERR_TIMEOUT) {
        const char* errMsg = "wifi connect timeout";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(board.rtcGetEpoch() + 60);
    }

    // Attempt to synchronize clocks with network time.
    err = configureTime(ntpHost, ntpTimezone);
    if (err != ESP_OK) {
        log(LOG_WARNING, "failed to synchronize RTC with network time");
    }

    if (mqttLoggerEnabled) {
        // Attempt to connect to MQTT broker for remote logging.
        err = configureMQTT(mqttLoggerBroker, mqttLoggerPort, mqttLoggerTopic,
                            mqttLoggerClientID, mqttLoggerRetries);
        if (err == ESP_ERR_TIMEOUT) {
            log(LOG_WARNING,
                "failed to connect remote logging, fallback to serial");
        }
    }

    // Reset err state.
    err = ESP_FAIL;
    const char* errMsg;
    int attempts = 0;

    int32_t defaultLen = E_INK_WIDTH * E_INK_HEIGHT * 8 + 100;
    uint8_t *buf = 0;
    // Default to a known refresh time.
    // (len("XX:XX:XX") = 8) + 1 = 9
    char nextRefreshTime[9] = FALLBACK_REFRESH_TIME;
    do {
        logf(LOG_DEBUG, "calendar download attempt #%d", attempts + 1);

        buf = downloadFile(serverURL, nextRefreshTime, &defaultLen);
        if (!buf) {
            errMsg = "file download error";
            log(LOG_ERROR, errMsg);
            continue;
        }
        err = ESP_OK;

        logf(LOG_INFO, "next refresh time: %s", nextRefreshTime);
#if defined(USE_SDCARD)
        err = writeFile(buf, defaultLen, CALENDAR_RW_PATH);
        if (err != ESP_OK) {
            errMsg = "file write error";
            log(LOG_ERROR, errMsg);
            continue;
        }
#endif
    } while (err != ESP_OK && ++attempts <= serverRetries);

    // Disconnect and turn off WiFi radio to save power.
    // Remove the below lines if you want to stay connected
    // and logging with MQTT, though more battery will be used.
    log(LOG_NOTICE, "disconnecting WiFi radio...");
    WiFi.disconnect();
    WiFi.mode(WIFI_OFF);

    // If we were not successful, print the error msg to the inkplate display.
    if (err != ESP_OK) {
        displayMessage(errMsg, batteryRemainingPercent);
        // Deep sleep until next refresh time
        sleep(nextRefreshTime);
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
    } while (err != ESP_OK && ++attempts <= serverRetries);

    // If we were not successful, print the error msg to the inkplate display.
    if (err != ESP_OK) {
        displayMessage(errMsg, batteryRemainingPercent);
    }

    // Deep sleep until next refresh time
    sleep(nextRefreshTime);
}

void loop() {}
