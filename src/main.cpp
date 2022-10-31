#define LOG_LEVEL LOG_DEBUG
#include "config.h"

RTC_DATA_ATTR int bootCount = 0;
RTC_DATA_ATTR time_t lastBootTime = 0;
RTC_DATA_ATTR time_t lastSleepTime = 0;
RTC_DATA_ATTR time_t targetWakeTime = 0;
RTC_DATA_ATTR unsigned long driftSecs = 0;

void setup() {
    ++bootCount;
    Serial.begin(115200);
    // Init inkplate board
    display.begin();
    // Set display to portait mode
    display.setRotation(1);

    time_t bootTime = display.rtcGetEpoch();
    logf(LOG_INFO, "boot count: %d", bootCount);
    logf(LOG_INFO, "boot time: %s", fmtTime(bootTime));

    esp_sleep_wakeup_cause_t wakeup_reason = esp_sleep_get_wakeup_cause();
    switch (wakeup_reason) {
        case ESP_SLEEP_WAKEUP_EXT0:
            logf(LOG_INFO, "wakeup caused by external signal using RTC_IO.");
            display.rtcClearAlarmFlag();
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

    // Init storage
    if (!display.sdCardInit()) {
        const char* errMsg = "SD card error";
        log(LOG_ERROR, errMsg);
        displayError(errMsg);
        sleep();
    }
    // If previous image exists, load into display buffer
    if (!display.drawImage(IMAGE_HOST_PATH, 0, 0, false, true)) {
        log(LOG_WARNING, "load previous calendar error");
    }

    // Get battery voltages before connecting to WiFi
    float bvoltCal = getCalibratedBatteryVoltage();
    // Get inkplate's calculation for reference
    float bvolt = display.readBattery();

    // Connect to WiFi
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    logf(LOG_INFO, "connecting to WiFi SSID %s...", WIFI_SSID);

    // Retry until success or give up
    int attempts = 0;
    while (attempts++ <= MAX_RETRIES && WiFi.status() != WL_CONNECTED) {
        delay(1000);
    }

    // If give up, display error to display
    if (WiFi.status() != WL_CONNECTED) {
        const char* errMsg = "WiFi connect timeout";
        log(LOG_ERROR, errMsg);
        displayError(errMsg);
        sleep();
    }
    // Print the IP address
    logf(LOG_INFO, "IP address: %s", WiFi.localIP().toString());

    // Set up remote logging with mqtt broker
    logf(LOG_INFO, "configuring remote logging...");
    mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
    attempts = 0;
    while (!mqttClient.connect(MQTT_CLIENT_ID)) {
        if (attempts++ >= MAX_RETRIES) {
            log(LOG_WARNING,
                "failed to connect remote logging, fallback to serial");
            break;
        }
        logf(LOG_WARNING, "mqtt connection failed, rc=%d", mqttClient.state());
        delay(250);
    }

    // Get time from NTP server
    timeClient.begin();
    timeClient.update();
    // Sync RTC with NTP time
    display.rtcSetEpoch(timeClient.getEpochTime());
    logf(LOG_DEBUG, "RTC synced to %s", fmtTime(display.rtcGetEpoch()));

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

    logf(LOG_INFO, "battery voltage: %sv", String(bvoltCal, 2));
    logf(LOG_DEBUG, "reference inkplate battery voltage: %sv",
         String(bvolt, 2));

    if (isVbusPresent()) {
        const char* bstat = (bvolt < 4.0) ? "charging" : "charged";
        logf(LOG_INFO, "USB power present - battery %s", bstat);
    } else if (bvolt > 0.0) {
        if (bvolt < 3.1) {
            log(LOG_NOTICE, "battery near empty! - sleeping until charged");
            displayError("Battery empty, please charge!");
            sleep();
        } else if (bvolt < 3.3) {
            log(LOG_WARNING, "battery low, charge soon!");
        } else {
            const char* bstat = (bvolt < 3.6) ? "below" : "above";
            logf(LOG_INFO, "battery approx %s 50%% capacity", bstat);
        }
    } else {
        log(LOG_WARNING, "problem detecting battery voltage");
    }

    // Format url
    char url[256];
    sprintf(url, "http://%s:%d%s", IMAGE_HOST, IMAGE_HOST_PORT,
            IMAGE_HOST_PATH);

    downloadImage(url, IMAGE_HOST_PATH);
    displayImage(IMAGE_HOST_PATH);
    sleep();
}

time_t getWakeTime() {
    if (!display.rtcIsSet()) {
        log(LOG_WARNING, "cannot determine wake time: RTC not set");
        return display.rtcGetEpoch() + FALLBACK_SLEEP_SECONDS;
    }

    tmElements_t tm;
    int hr, min, sec;
    sscanf(DAILY_WAKE_TIME, "%d:%d:%d", &hr, &min, &sec);

    tm.Hour = hr;
    tm.Minute = min;
    tm.Second = sec;
    tm.Day = display.rtcGetDay();
    tm.Month = display.rtcGetMonth();
    tm.Year = CalendarYrToTm(display.rtcGetYear());

    time_t targetTime = makeTime(tm);
    time_t nowTime = display.rtcGetEpoch();

    // Rollover to tomorrow
    if (nowTime > targetTime) {
        targetTime += SECS_PER_DAY;
    }

    return targetTime;
}

void sleep() {
    targetWakeTime = getWakeTime();

    log(LOG_NOTICE, "deep sleep initiated");
    logf(LOG_DEBUG, "RTC time now is %s", fmtTime(display.rtcGetEpoch()));
    logf(LOG_DEBUG, "setting deep sleep RTC wakeup on pin %d", GPIO_NUM_39);

    display.rtcSetAlarmEpoch(targetWakeTime, RTC_ALARM_MATCH_DHHMMSS);
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_39, 0);

    logf(LOG_INFO, "waking at %s", fmtTime(targetWakeTime));
    log(LOG_NOTICE, "deep sleeping in 5 seconds");
    delay(5000);

    WiFi.mode(WIFI_OFF);
    lastSleepTime = display.rtcGetEpoch();
    esp_deep_sleep_start();
}

void downloadImage(const char* url, const char* filePath) {
    logf(LOG_INFO, "downloading image at URL %s", url);

    // Guestimate file size for PNG image @ 1200x825
    int32_t len = E_INK_WIDTH * E_INK_HEIGHT * 4 + 100;
    // Download file from URL
    uint8_t* buf = display.downloadFile(url, &len);
    if (!buf) {
        const char* errMsg = "image download error";
        log(LOG_ERROR, errMsg);
        displayError(errMsg);
        sleep();
    }

    logf(LOG_INFO, "writing image data to path %s", filePath);
    SdFat sd = display.getSdFat();

    // Write image buffer to SD card
    if (sd.exists(filePath)) {
        sd.remove(filePath);
    }

    File sdfile = sd.open(filePath, FILE_WRITE);
    if (!sdfile) {
        const char* errMsg = "file write error";
        log(LOG_ERROR, errMsg);
        displayError(errMsg);
        sleep();
    }

    sdfile.write(buf, len);
    sdfile.close();
}

void displayImage(const char* filePath) {
    logf(LOG_INFO, "drawing image from path: %s", filePath);

    bool ok = false;
    int attempts = 0;
    while (!ok && ++attempts <= MAX_RETRIES) {
        logf(LOG_DEBUG, "draw attempt #%d", attempts);

        if (attempts > 1) {
            delay(5000);
        }

        display.clearDisplay();
        if (!display.drawImage(filePath, 0, 0, false, true)) {
            log(LOG_ERROR, "image draw error");
            continue;
        }
        display.display();

        logf(LOG_INFO, "draw attempt #%d success", attempts);
        ok = true;
    }

    if (!ok) displayError("Calendar refresh failed");
}

void displayError(const char* msg) {
    display.setTextSize(4);
    display.setTextColor(1, 0);
    display.setTextWrap(true);
    display.setCursor(0, 0);
    display.print(msg);
    display.display();
}

void loop() {}