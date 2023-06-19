#include <ArduinoJson.h>
#include <ArduinoYaml.h>
#include <SdFat.h>
#include <StreamUtils.h>

#include "lib.h"
#include "battery.h"

void setup() {
    Serial.begin(115200);
    // Init inkplate board.
    board.begin();
    // Set board to portait mode.
    board.setRotation(1);

    log(LOG_NOTICE, "##### Inkplate10 Weather Calendar wake up #####");

    // Set clock from RTC
    board.rtcGetRtcData();
    time_t bootTime = board.rtcGetEpoch();
    setTime(bootTime);

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
    float bvolt = board.readBattery();
    logf(LOG_INFO, "battery voltage: %sv", String(bvolt, 2));
    // Get the battery percentage remaining.
    int batteryRemainingPercent = getBatteryCapacity(bvolt);
    logf(LOG_INFO, "approx battery capacity: %d%%", batteryRemainingPercent);

    if (batteryRemainingPercent <= 1) {
        log(LOG_NOTICE, "battery near empty! - sleeping until charged");
        displayMessage("Battery empty, please charge!", batteryRemainingPercent);
        // Sleep instead of proceeding when battery is too low.
        sleep(SECONDS_IN_YEAR);
    } else if (batteryRemainingPercent <= 10) {
        log(LOG_WARNING, "battery low, charge soon!");
    }

    // Init err state.
    esp_err_t err = ESP_OK;

    // Init storage.
    if (!board.sdCardInit()) {
        const char* errMsg = "SD card init failure";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(CONFIG_DEFAULT_CALENDAR_DAILY_REFRESH_TIME);
    }

    // Attempt to get config yaml file.
    File file = sd.open(CONFIG_FILE_PATH, FILE_READ);
    if (!file) {
        const char* errMsg = "Failed to open config file";
        logf(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(CONFIG_DEFAULT_CALENDAR_DAILY_REFRESH_TIME);
    }

    // Attempt to parse yaml file.
    StaticJsonDocument<768> doc;
    ReadBufferingStream bufferedFile(file, 64);
    DeserializationError dse = deserializeYml(doc, bufferedFile);
    if (dse) {
        const char* errMsg = "Failed to load config from file";
        logf(LOG_ERROR, "failed to deserialize YAML: %s", dse.c_str());
        displayMessage(errMsg, batteryRemainingPercent);
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
    const char* ntpTimezone = doc["ntp"]["timezone"];

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
        displayMessage(errMsg, batteryRemainingPercent);
        sleep(calendarDailyRefreshTime);
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
    do {
        logf(LOG_DEBUG, "calendar download attempt #%d", attempts + 1);

        err = downloadFile(calendarUrl, CALENDAR_IMAGE_SIZE, CALENDAR_RW_PATH);
        if (err != ESP_OK) {
            errMsg = "file download error";
            log(LOG_ERROR, errMsg);
            continue;
        }
    } while (err != ESP_OK && ++attempts <= calendarRetries);

    // Disconnect and turn off WiFi radio to save power.
    // Remove the below lines if you want to stay connected
    // and logging with MQTT, though more battery will be used.
    log(LOG_NOTICE, "disconnecting WiFi radio...");
    WiFi.disconnect();
    WiFi.mode(WIFI_OFF);

    // If we were not successful, print the error msg to the inkplate display.
    if (err != ESP_OK) {
        displayMessage(errMsg, batteryRemainingPercent);
    }
    
    // Reset err state.
    err = ESP_FAIL;
    attempts = 0;
    do {
        logf(LOG_DEBUG, "calendar draw attempt #%d", attempts + 1);

        board.clearDisplay();
        err = loadImage(CALENDAR_RW_PATH);
        if (err != ESP_OK) {
            errMsg = "image load error";
            log(LOG_ERROR, errMsg);
            continue;
        }

        displayBatteryStatus(batteryRemainingPercent, false);

        // Send buffer to eink display.
        board.display();
    } while (err != ESP_OK && ++attempts <= calendarRetries);

    // If we were not successful, print the error msg to the inkplate display.
    if (err != ESP_OK) {
        displayMessage(errMsg, batteryRemainingPercent);
    }

    // Deep sleep until next refresh time
    sleep(calendarDailyRefreshTime);
}

void loop() {}
