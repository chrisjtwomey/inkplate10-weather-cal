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
// inkplate10 board driver
Inkplate board(INKPLATE_3BIT);

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
    board.rtcGetRtcData();

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
    sprintf(prefix, "%s - %s - ", fmtTime(board.rtcGetEpoch()), priority);
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

    mqttLogger.println(buf);
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
    mqttLogger.println(b);
    va_end(args);
}

/**
  Gets a reading of the battery voltage by a calibrated ADC.

  @returns a float of the battery voltage.
*/
float getCalibratedBatteryVoltage() {
    // calibration factor - adjust until correlates with actual readings
    float calibration = 2.140;
    // default voltage reference for esp32
    float vref = 1100;

    // get characterized voltage reference
    esp_adc_cal_characteristics_t adcChars;
    esp_adc_cal_characterize(ADC_UNIT_1, ADC_ATTEN_DB_11, ADC_WIDTH_BIT_12,
                             vref, &adcChars);
    vref = adcChars.vref;

    uint8_t mcpRegsInt[22];
    board.pinModeInternal(IO_INT_ADDR, mcpRegsInt, 9, INPUT);
    int state = board.digitalReadInternal(IO_INT_ADDR, mcpRegsInt, 9);
    board.pinModeInternal(IO_INT_ADDR, mcpRegsInt, 9, OUTPUT);

    if (state) {
        board.digitalWriteInternal(IO_INT_ADDR, mcpRegsInt, 9, LOW);
    } else {
        board.digitalWriteInternal(IO_INT_ADDR, mcpRegsInt, 9, HIGH);
    }

    delay(1);
    int adc = analogRead(35);
    if (state) {
        board.pinModeInternal(IO_INT_ADDR, mcpRegsInt, 9, INPUT);
    } else {
        board.digitalWriteInternal(IO_INT_ADDR, mcpRegsInt, 9, LOW);
    }

    return (adc / 4095.0) * 3.3 * (1100 / vref) * calibration;
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
  @param gmtOffset the timezone offset from GMT in hours. (eg. 0 == GMT, 1 ==
  GMT+1). error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_ENTP if updating the NTP client fails.
*/
esp_err_t configureTime(const char* host, int gmtOffset) {
    WiFiUDP udp;
    NTPClient ntp(udp, host, gmtOffset * 60 * 60, 60000);
    ntp.begin();
    if (!ntp.update() || !ntp.isTimeSet()) {
        return ESP_ERR_ENTP;
    }

    // Sync RTC with NTP time
    board.rtcSetEpoch(ntp.getEpochTime());
    logf(LOG_DEBUG, "RTC synced to %s", fmtTime(board.rtcGetEpoch()));

    return ESP_OK;
}

/**
  Format epoch time.

  @returns a representation of epoch time in the format DD:MM:YY HH:MM:SS
*/
const char* fmtTime(uint32_t t) {
    char* tstr = new char[20];
    sprintf(tstr, "%02d-%02d-%04d %02d:%02d:%02d", day(t), month(t), year(t),
            hour(t), minute(t), second(t));
    return tstr;
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
    tm.Day = board.rtcGetDay();
    tm.Month = board.rtcGetMonth();
    tm.Year = CalendarYrToTm(board.rtcGetYear());

    time_t targetTime = makeTime(tm);
    time_t nowTime = board.rtcGetEpoch();

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
    logf(LOG_DEBUG, "RTC time now is %s", fmtTime(board.rtcGetEpoch()));
    logf(LOG_DEBUG, "setting deep sleep RTC wakeup on pin %d", GPIO_NUM_39);

    board.rtcSetAlarmEpoch(targetWakeTime, RTC_ALARM_MATCH_DHHMMSS);
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_39, 0);

    logf(LOG_INFO, "waking at %s", fmtTime(targetWakeTime));
    log(LOG_NOTICE, "deep sleeping in 5 seconds");
    delay(5000);

    WiFi.mode(WIFI_OFF);
    lastSleepTime = board.rtcGetEpoch();
    esp_deep_sleep_start();
}