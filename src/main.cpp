#include <ArduinoJson.h>
#include <ArduinoYaml.h>
#include <SdFat.h>
#include <StreamUtils.h>

#include "lib.h"

void setup() {
    ++bootCount;
    Serial.begin(115200);
    // Init inkplate board.
    board.begin();
    // Set board to portait mode.
    board.setRotation(1);

    time_t bootTime = board.rtcGetEpoch();
    logf(LOG_INFO, "boot count: %d", bootCount);
    logf(LOG_INFO, "boot time: %s", fmtTime(bootTime));

    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    switch (wakeup_reason) {
        case ESP_SLEEP_WAKEUP_EXT0:
            logf(LOG_INFO, "wakeup caused by external signal using RTC_IO.");
            board.rtcClearAlarmFlag();
            break;
        case ESP_SLEEP_WAKEUP_EXT1:
            logf(LOG_INFO, "wakeup caused by external signal using RTC_CNTL.");
            break;
        case ESP_SLEEP_WAKEUP_TIMER:
            logf(LOG_INFO, "wakeup caused by timer.");
            break;
        case ESP_SLEEP_WAKEUP_TOUCHPAD:
            logf(LOG_INFO, "wakeup caused by touchpad.");
            break;
        case ESP_SLEEP_WAKEUP_ULP:
            logf(LOG_INFO, "wakeup caused by ULP program.");
            break;
        default:
            log(LOG_INFO, "wakeup caused by RST pin or power button");
            break;
    }

    // Init err state.
    esp_err_t err = ESP_OK;

    // Init storage.
    if (board.sdCardInit()) {
        // If previous image exists, load into board buffer.
        err = displayImage(CALENDAR_RW_PATH);
        if (err != ESP_OK) {
            log(LOG_WARNING, "load previous calendar error");
        }
    } else {
        const char* errMsg = "SD card init failure";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg);
        sleep(CONFIG_DEFAULT_CALENDAR_DAILY_REFRESH_TIME);
    }

    // Attempt to get config yaml file.
    File file = sd.open(CONFIG_FILE_PATH, FILE_READ);
    if (!file) {
        const char* errMsg = "Failed to open config file";
        logf(LOG_ERROR, errMsg);
        displayMessage(errMsg);
        sleep(CONFIG_DEFAULT_CALENDAR_DAILY_REFRESH_TIME);
    }

    // Attempt to parse yaml file.
    StaticJsonDocument<768> doc;
    ReadBufferingStream bufferedFile(file, 64);
    DeserializationError dse = deserializeYml(doc, bufferedFile);
    if (dse) {
        const char* errMsg = "Failed to load config from file";
        logf(LOG_ERROR, "failed to deserialize YAML: %s", dse.c_str());
        displayMessage(errMsg);
        sleep(CONFIG_DEFAULT_CALENDAR_DAILY_REFRESH_TIME);
    }
    file.close();

    // Assign config values.
    JsonObject calendarCfg = doc["calendar"];
    const char* calendarUrl = calendarCfg["url"];
    const char* calendarDailyRefreshTime = calendarCfg["daily_refresh_time"];
    int calendarRetries = calendarCfg["retries"];

    // Wifi config.
    JsonObject wifiCfg = doc["wifi"];
    const char* wifiSSID = wifiCfg["ssid"];
    const char* wifiPass = wifiCfg["pass"];
    int wifiRetries = wifiCfg["retries"];

    // NTP config.
    const char* ntpHost = doc["ntp"]["host"];
    int ntpGMTOffset = doc["ntp"]["gmt_offset"];

    // Remote logging config.
    JsonObject mqttLoggerCfg = doc["mqtt_logger"];
    bool mqttLoggerEnabled = mqttLoggerCfg["enabled"];
    const char* mqttLoggerBroker = mqttLoggerCfg["broker"];
    int mqttLoggerPort = mqttLoggerCfg["port"];
    const char* mqttLoggerClientID = mqttLoggerCfg["clientId"];
    const char* mqttLoggerTopic = mqttLoggerCfg["topic"];
    int mqttLoggerRetries = mqttLoggerCfg["retries"];

    // Attempt to connect to WiFi.
    err = configureWiFi(wifiSSID, wifiPass, wifiRetries);
    if (err == ESP_ERR_TIMEOUT) {
        const char* errMsg = "wifi connect timeout";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg);
        sleep(calendarDailyRefreshTime);
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

    // Attempt to synchronize real-time clock with network time.
    err = configureTime(ntpHost, ntpGMTOffset);
    if (err != ESP_OK) {
        log(LOG_WARNING, "failed to synchronize RTC with network time");
    }

    // Print some information about sleep and wake times.
    if (lastBootTime > 0) {
        logf(LOG_INFO, "last boot time: %s", fmtTime(lastBootTime));
    }
    lastBootTime = bootTime;

    if (lastSleepTime > 0) {
        logf(LOG_INFO, "last sleep time: %s", fmtTime(lastSleepTime));
    }

    if (targetWakeTime > 0) {
        logf(LOG_INFO, "expected wake time: %s", fmtTime(targetWakeTime));
        driftSecs = targetWakeTime - bootTime;
    }

    if (driftSecs > 0) {
        logf(LOG_INFO, "time drift: %d seconds", driftSecs);
    }

    // Read battery voltage.
    // TODO: might be worth investigating whether this readings are affected
    // when connected to WiFi.
    float bvoltCal = getCalibratedBatteryVoltage();
    // Get inkplate's battery calculation for reference.
    float bvolt = board.readBattery();
    logf(LOG_INFO, "battery voltage: %sv", String(bvoltCal, 2));
    logf(LOG_DEBUG, "reference inkplate battery voltage: %sv",
         String(bvolt, 2));

    if (isVbusPresent()) {
        const char* bstat = (bvolt < 4.0) ? "charging" : "charged";
        logf(LOG_INFO, "USB power present - battery %s", bstat);
    } else if (bvolt > 0.0) {
        if (bvolt < 3.1) {
            log(LOG_NOTICE, "battery near empty! - sleeping until charged");
            displayMessage("Battery empty, please charge!");
            // Sleep instead of proceeding when battery is too low.
            sleep(calendarDailyRefreshTime);
        } else if (bvolt < 3.3) {
            log(LOG_WARNING, "battery low, charge soon!");
        } else {
            const char* bstat = (bvolt < 3.6) ? "below" : "above";
            logf(LOG_INFO, "battery approx %s 50%% capacity", bstat);
        }
    } else {
        log(LOG_WARNING, "problem detecting battery voltage");
    }

    // Reset err state.
    err = ESP_FAIL;
    int attempts = 0;
    do {
        logf(LOG_DEBUG, "calendar refresh attempt #%d", attempts + 1);

        err = downloadFile(calendarUrl, CALENDAR_IMAGE_SIZE, CALENDAR_RW_PATH);
        if (err == ESP_OK) {
            err = displayImage(CALENDAR_RW_PATH);
        }
    } while (err != ESP_OK && ++attempts <= calendarRetries);

    // If we were not successfully, print the error msg to the inkplate display.
    if (err != ESP_OK) {
        const char* errMsg;
        if (err == ESP_ERR_EDRAW) {
            errMsg = "image draw error";
            log(LOG_ERROR, errMsg);
            displayMessage(errMsg);
        } else if (err == ESP_ERR_EDL) {
            errMsg = "file download error";
            log(LOG_ERROR, errMsg);
            displayMessage(errMsg);
        } else if (err == ESP_ERR_EFILEW) {
            errMsg = "sd card file write error";
            log(LOG_ERROR, errMsg);
        } else {
            errMsg = "unexpected error downloading file";
            log(LOG_ERROR, errMsg);
            displayMessage(errMsg);
        }
    }

    // Deep sleep until next refresh time
    sleep(calendarDailyRefreshTime);
}

void loop() {}
