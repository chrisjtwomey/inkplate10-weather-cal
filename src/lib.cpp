#include "lib.h"

// The number of times we have booted (from off or from sleep).
RTC_DATA_ATTR int bootCount = 0;
// RTC epoch of the last time we booted.
RTC_DATA_ATTR time_t lastBootTime = 0;
// RTC epoch of the last time deep sleep was initiated.
RTC_DATA_ATTR time_t lastSleepTime = 0;
// RTC epoch of the time in the future when we want to end deep sleep.
RTC_DATA_ATTR time_t targetWakeTime = 0;
// The number of seconds between RTC epoch and NTP epoch.
RTC_DATA_ATTR unsigned long driftSecs = 0;

// remote mqtt logger
WiFiClient espClient;
PubSubClient client(espClient);
MqttLogger mqttLogger(client, "", MqttLoggerMode::SerialOnly);
// queue to store messages to publish once mqtt connection is established.
cppQueue logQ(sizeof(char) * 100, LOG_QUEUE_MAX_ENTRIES, FIFO, true);
// inkplate10 board driver
Inkplate board(INKPLATE_3BIT);
// timezone store
Timezone myTz;

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
esp_err_t configureWiFi(const char* ssid, const char* pass, int retries) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);
    logf(LOG_INFO, "connecting to WiFi SSID %s...", ssid);

    // Retry until success or give up
    int attempts = 0;
    while (attempts++ <= retries && WiFi.status() != WL_CONNECTED) {
        logf(LOG_DEBUG, "connection attempt #%d...", attempts);
        delay(1000);
    }

    // If still not connected, error with timeout.
    if (WiFi.status() != WL_CONNECTED) {
        return ESP_ERR_TIMEOUT;
    }
    // Print the IP address
    logf(LOG_INFO, "IP address: %s", WiFi.localIP().toString());

    return ESP_OK;
}

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
esp_err_t downloadFile(const char* url, int32_t size, const char* filePath) {
    logf(LOG_INFO, "downloading file at URL %s", url);

    // Download file from URL
    uint8_t* buf = board.downloadFile(url, &size);
    if (!buf) {
        return ESP_ERR_EDL;
    }

    logf(LOG_INFO, "writing file to path %s", filePath);
    SdFat sd = board.getSdFat();

    // Write image buffer to SD card
    if (sd.exists(filePath)) {
        sd.remove(filePath);
    }

    File sdfile = sd.open(filePath, FILE_WRITE);
    if (!sdfile) {
        return ESP_ERR_EFILEW;
    }

    sdfile.write(buf, size);
    sdfile.close();

    return ESP_OK;
}

/**
  Draw an image to the display.

  @param filePath the path of the file on disk.
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t displayImage(const char* filePath) {
    logf(LOG_INFO, "drawing image from path: %s", filePath);

    board.clearDisplay();
    if (!board.drawImage(filePath, 0, 0, false, true)) {
        return ESP_ERR_EDRAW;
    }
    board.display();

    return ESP_OK;
}

/**
  Draw an message to the display. The error message is drawn in the top-left
  corner of the display. Error message will overlay previously drawn image.

  @param msg the message to display.
  error.
*/
void displayMessage(const char* msg) {
    board.setTextSize(4);
    board.setTextColor(1, 0);
    board.setTextWrap(true);
    board.setCursor(0, 0);
    board.print(msg);
    board.display();
}

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
                        const char* clientID, int max_retries) {
    log(LOG_INFO, "configuring remote MQTT logging...");

    client.setServer(broker, port);
    // Attempt to connect to MQTT broker.
    int attempts = 0;
    while (attempts++ <= max_retries && !client.connect(clientID)) {
        logf(LOG_DEBUG, "connection attempt #%d...", attempts);
        delay(250);
    }

    if (!client.connected()) {
        return ESP_ERR_TIMEOUT;
    }

    mqttLogger.setTopic(topic);
    mqttLogger.setMode(MqttLoggerMode::MqttAndSerial);

    // Print the IP address
    logf(LOG_INFO, "connected to MQTT broker %s:%d", broker, port);

    return ESP_OK;
}

/**
  Converts a priority into a log level prefix.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @returns the string value of the priority.
*/
const char* msgPrefix(uint16_t pri) {
    char* priority;

    switch (pri) {
        case LOG_CRIT:
            priority = (char*)"CRITICAL";
            break;
        case LOG_ERROR:
            priority = (char*)"ERROR";
            break;
        case LOG_WARNING:
            priority = (char*)"WARNING";
            break;
        case LOG_NOTICE:
            priority = (char*)"NOTICE";
            break;
        case LOG_INFO:
            priority = (char*)"INFO";
            break;
        case LOG_DEBUG:
            priority = (char*)"DEBUG";
            break;
        default:
            priority = (char*)"INFO";
            break;
    }

    char* prefix = new char[35];
    sprintf(prefix, "%s - %s - ", myTz.dateTime(RFC3339).c_str(), priority);
    return prefix;
}

/**
  Log a message.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param msg the message to log.
*/
void log(uint16_t pri, const char* msg) {
    if (pri > LOG_LEVEL) return;

    const char* prefix = msgPrefix(pri);
    size_t prefixLen = strlen(prefix);
    size_t msgLen = strlen(msg);
    char buf[prefixLen + msgLen + 1];
    strcpy(buf, prefix);
    strcat(buf, msg);
    ensureQueue(buf);
}

/**
  Log a message with formatting.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param fmt the format of the log message
*/
void logf(uint16_t pri, const char* fmt, ...) {
    if (pri > LOG_LEVEL) return;

    const char* prefix = msgPrefix(pri);
    size_t prefixLen = strlen(prefix);
    size_t msgLen = strlen(fmt);
    char a[prefixLen + msgLen + 1];
    strcpy(a, prefix);
    strcat(a, fmt);

    va_list args;
    va_start(args, fmt);
    size_t size = snprintf(NULL, 0, a, args);
    char b[size + 1];
    vsprintf(b, a, args);
    ensureQueue(b);
    va_end(args);
}

/**
  Ensure log queue is populated/emptied based on MQTT connection.

  @param msg the log message.
*/
void ensureQueue(char* logMsg) {
    if (!client.connected()) {
        // populate log queue while no mqtt connection
        logQ.push(logMsg);
    } else {
        // send queued logs once we are connected.
        if (logQ.getCount() > 0) {
            mqttLogger.setMode(MqttLoggerMode::MqttOnly);
            while (!logQ.isEmpty()) {
                logQ.pop(logMsg);
                mqttLogger.println(logMsg);
            }
            mqttLogger.setMode(MqttLoggerMode::MqttAndSerial);
        }
    }
    // print/send the current log
    mqttLogger.println(logMsg);
}

/**
  Check whether 5v USB power is detected.

  @returns a boolean whether 5v USB power is detected.
*/
bool isVbusPresent() {
    // TODO: determine USB power?
    return false;
}

/**
  Connect to an NTP server and synchronize the on-board real-time clock.

  @param host the hostname of the NTP server (eg. pool.ntp.org).
  @param timezoneName the name of the timezone in Olson format (eg.
  Europe/Dublin)
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_ENTP if updating the NTP client fails.
*/
esp_err_t configureTime(const char* ntpHost, const char* timezoneName) {
    log(LOG_INFO, "configuring network time and RTC...");

    setServer(ntpHost);

    if (!waitForSync()) {
        return ESP_ERR_ENTP;
    }
    myTz.setLocation(F(timezoneName));

    updateNTP();
    // Sync RTC with NTP time
    // time_t nowTime = now();
    time_t nowTime = myTz.now();
    board.rtcSetEpoch(nowTime);
    logf(LOG_INFO, "RTC synced to %s", dateTime(nowTime, RFC3339).c_str());

    return ESP_OK;
}

/**
  Get the next scheduled time to wake from deep sleep.

  @param refreshTime the time of the day to wake in HH::MM:SS format (eg.
  09:00:00). error.
  @returns the epoch time of when to wake.
  If the real-time clock is not configured, it will return the last configured
  RTC epoch time + DEEP_SLEEP_FALLBACK_SECONDS.
*/
time_t getWakeTime(const char* refreshTime) {
    if (!board.rtcIsSet()) {
        log(LOG_WARNING, "cannot determine wake time: RTC not set");
        return board.rtcGetEpoch() + DEEP_SLEEP_FALLBACK_SECONDS;
    }

    tmElements_t tm;
    int hr, min, sec;
    sscanf(refreshTime, "%d:%d:%d", &hr, &min, &sec);

    tm.Hour = hr;
    tm.Minute = min;
    tm.Second = sec;

    tm.Day = myTz.day();
    tm.Month = myTz.month();
    tm.Year = CalendarYrToTm(myTz.year());

    time_t targetTime = makeTime(tm);
    time_t nowTime = myTz.now();

    // Rollover to tomorrow
    if (nowTime > targetTime) {
        targetTime += SECS_PER_DAY;
    }

    return targetTime;
}

/**
  Enter deep sleep.

  @param refreshTime the time of the day to wake in HH:MM:SS format (eg.
  09:00:00). error.
*/
void sleep(const char* refreshTime) {
    targetWakeTime = getWakeTime(refreshTime);

    log(LOG_NOTICE, "deep sleep initiated");
    time_t rtcTime = board.rtcGetEpoch();
    logf(LOG_DEBUG, "RTC time now is %s", dateTime(rtcTime, RFC3339).c_str());
    logf(LOG_DEBUG, "setting deep sleep RTC wakeup on pin %d", GPIO_NUM_39);

    board.rtcSetAlarmEpoch(targetWakeTime, RTC_ALARM_MATCH_DHHMMSS);
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_39, 0);

    logf(LOG_INFO, "waking at %s", dateTime(targetWakeTime, RFC3339).c_str());
    log(LOG_NOTICE, "deep sleeping in 5 seconds");
    delay(5000);

    WiFi.mode(WIFI_OFF);
    lastSleepTime = rtcTime;
    esp_deep_sleep_start();
}