#include <Inkplate.h>
#include <MqttLogger.h>
#include <NTPClient.h>
#include <PubSubClient.h>
#include <TimeLib.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/rtc_io.h>
#include <rom/rtc.h>

#define WIFI_SSID "XXXX"  // replace with your WiFi SSID
#define WIFI_PASS "XXXX"  // replace with your WiFi password
#define MAX_RETRIES 3     // max times to retry connection

#ifndef IMAGE_HOST
#define IMAGE_HOST "localhost"  // the image host
#endif

#ifndef IMAGE_HOST_PORT
#define IMAGE_HOST_PORT 8080
#endif

#ifndef IMAGE_HOST_PATH
#define IMAGE_HOST_PATH "/calendar.png"
#endif

#ifndef DAILY_WAKE_TIME
#define DAILY_WAKE_TIME "07:00:00"  // the time everyday to refresh
#endif

#ifndef NTP_HOST
#define NTP_HOST "europe.pool.ntp.org"
#endif
#ifndef GMT_OFFSET
#define GMT_OFFSET 1  // +X timezone (eg. GMT+1)
#endif
#define FALLBACK_SLEEP_SECONDS 120  // seconds to sleep if RTC not configured

WiFiUDP udpClient;
NTPClient timeClient(udpClient, NTP_HOST, GMT_OFFSET * 60 * 60, 60000);

// inkplate10 board driver
Inkplate display(INKPLATE_3BIT);

#ifndef MQTT_BROKER
#define MQTT_BROKER "localhost"
#endif
#ifndef MQTT_PORT
#define MQTT_PORT 1883
#endif
#ifndef MQTT_CLIENT_ID
#define MQTT_CLIENT_ID "eink-cal-client"
#endif
#define MQTT_TOPIC "mqtt/eink-cal-client"
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
MqttLogger mqttLogger(mqttClient, MQTT_TOPIC, MqttLoggerMode::MqttAndSerial);

#define LOG_CRIT 0
#define LOG_ERROR 1
#define LOG_WARNING 2
#define LOG_NOTICE 3
#define LOG_INFO 4
#define LOG_DEBUG 5
#ifndef LOG_LEVEL
#define LOG_LEVEL LOG_INFO
#endif

const char* fmtTime(uint32_t t) {
    char* tstr = new char[20];
    sprintf(tstr, "%02d-%02d-%04d %02d:%02d:%02d", day(t), month(t), year(t),
            hour(t), minute(t), second(t));
    return tstr;
}

const char* msgPrefix(uint16_t pri) {
    display.rtcGetRtcData();
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
    sprintf(prefix, "%s - %s - ", fmtTime(display.rtcGetEpoch()), priority);
    return prefix;
}

void log(uint16_t pri, const char* msg) {
    if (pri > LOG_LEVEL) return;

    const char* prefix = msgPrefix(pri);
    size_t len_prefix = strlen(prefix);
    size_t len_msg = strlen(msg);
    char buf[len_prefix + len_msg + 1];
    strcpy(buf, prefix);
    strcat(buf, msg);

    mqttLogger.println(buf);
}

void logf(uint16_t pri, const char* fmt, ...) {
    if (pri > LOG_LEVEL) return;

    const char* prefix = msgPrefix(pri);
    size_t len_prefix = strlen(prefix);
    size_t len_msg = strlen(fmt);
    char a[len_prefix + len_msg + 1];
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

void setup();
void sleep();
bool isVbusPresent();
time_t getWakeTime();
float getBatteryVoltage();
void displayImage(const char* host, const int port, const char* path, int16_t x,
                  int16_t y);
