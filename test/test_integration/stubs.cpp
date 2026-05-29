// Stub implementations for all free functions called by app.cpp that are NOT
// compiled in the native_integration environment (network_utils, display_utils,
// sleep_utils, battery, log_utils, time_utils).
//
// Each stub records the call in the corresponding *Stubs struct so tests can
// assert on what was invoked and with what arguments.

#ifdef NATIVE

#include <stdarg.h>
#include <string.h>
#include "integration_stubs.h"

// Pull in headers that declare the functions we are defining.
#include "log_utils.h"        // log(), logf(), configureMQTT()
#include "network_utils.h"    // configureWiFi(), configureTime(), downloadFile()
#include "display_utils.h"    // loadImage(), displayBatteryStatus(), displayMessage(),
                              // saveCalendarCache()
#include "sleep_utils.h"      // sleep_for(), sleep(), deepSleep()
#include "battery.h"          // getBatteryCapacity()
#include "time_utils.h"       // nowTzFmt()
#include "WiFi.h"
#include "SPIFFS.h"
#include "Arduino.h"          // HardwareSerial, g_wakeup_cause

// ---------------------------------------------------------------------------
// Global stub state
// ---------------------------------------------------------------------------
NetworkStubs netStubs;
DisplayStubs dispStubs;
SleepStubs   sleepStubs;
BatteryStubs batteryStubs;

void resetAllStubs() {
    netStubs.reset();
    dispStubs.reset();
    sleepStubs.reset();
    batteryStubs.reset();
}

// ---------------------------------------------------------------------------
// Global singletons referenced by stub headers / app.cpp
// ---------------------------------------------------------------------------
WiFiClass    WiFi;
SPIFFSClass  SPIFFS;
HardwareSerial Serial;
esp_sleep_wakeup_cause_t g_wakeup_cause = ESP_SLEEP_WAKEUP_UNDEFINED;

// ---------------------------------------------------------------------------
// Logging stubs (conflict with math.h log/logf on macOS — include log_utils.h
// so the guard fires rather than redeclaring as C functions)
// ---------------------------------------------------------------------------
void log(uint16_t, const char*) {}
void logf(uint16_t, const char*, ...) {}
esp_err_t configureMQTT(const char*, int, const char*, const char*, int) {
    return netStubs.mqttResult;
}

// ---------------------------------------------------------------------------
// time_utils stub
// ---------------------------------------------------------------------------
String nowTzFmt() { return ""; }

// ---------------------------------------------------------------------------
// battery stub
// ---------------------------------------------------------------------------
int getBatteryCapacity(double) {
    return batteryStubs.capacity;
}

// ---------------------------------------------------------------------------
// network_utils stubs
// ---------------------------------------------------------------------------
esp_err_t configureWiFi(const char*, const char*, int) {
    return netStubs.wifiResult;
}

esp_err_t configureTime(const char*, const char*) {
    return netStubs.timeResult;
}

uint8_t* downloadFile(const char* url, uint32_t* nextRefreshSecs,
                      int32_t* size, char* nextURL, size_t nextURLSize) {
    netStubs.downloadCallCount++;
    netStubs.lastDownloadURL = url;
    if (netStubs.downloadBuf != nullptr) {
        *nextRefreshSecs = netStubs.downloadNextRefresh;
        *size = netStubs.downloadBufLen;
        if (nextURL && nextURLSize > 0) {
            if (netStubs.downloadNextURL && netStubs.downloadNextURL[0]) {
                strncpy(nextURL, netStubs.downloadNextURL, nextURLSize - 1);
                nextURL[nextURLSize - 1] = '\0';
            }
        }
    }
    return netStubs.downloadBuf;
}

// ---------------------------------------------------------------------------
// display_utils stubs
// ---------------------------------------------------------------------------
esp_err_t loadImage(const char*) {
    dispStubs.loadImageCallCount++;
    return dispStubs.loadImageResult;
}

esp_err_t loadImage(uint8_t*, int32_t) {
    dispStubs.loadImageCallCount++;
    return dispStubs.loadImageResult;
}

esp_err_t loadImage(uint8_t*, int, int, int, int) {
    dispStubs.loadImageCallCount++;
    return dispStubs.loadImageResult;
}

void displayBatteryStatus(int percent, bool invert) {
    dispStubs.displayBatteryCallCount++;
    dispStubs.lastBatteryPercent = percent;
    dispStubs.lastBatteryInvert  = invert;
}

void displayMessage(const char* msg, int) {
    dispStubs.displayMessageCalled = true;
    dispStubs.lastDisplayMsg       = msg;
}

bool saveCalendarCache(const uint8_t*, int32_t) {
    dispStubs.saveCalendarCacheCalled = true;
    return dispStubs.saveCalendarCacheResult;
}

// ---------------------------------------------------------------------------
// sleep_utils stubs
// ---------------------------------------------------------------------------
void sleep_for(uint32_t seconds) {
    sleepStubs.sleepForCalled   = true;
    sleepStubs.lastSleepForSecs = seconds;
}

void sleep(time_t epoch) {
    sleepStubs.sleepCalled    = true;
    sleepStubs.lastSleepEpoch = epoch;
}

void deepSleep() {}

#endif // NATIVE
