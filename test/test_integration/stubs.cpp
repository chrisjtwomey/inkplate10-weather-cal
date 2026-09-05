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
                              // saveImageCache()
#include "sleep_utils.h"      // sleep_for(), sleep(), deepSleep()
#include "battery.h"          // getBatteryCapacity()
#include "time_utils.h"       // nowTzFmt()
#include "ota.h"              // otaTrialPending(), otaConfirm(), otaRollback(),
                              // applyFirmwareUpdate()
#include "wake.h"             // the steps run_app() is built from
#include "settings.h"         // loadConfig()
#include "defaults.h"         // the compiled values loadConfig() reports
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
OtaStubs     otaStubs;

void resetAllStubs() {
    netStubs.reset();
    dispStubs.reset();
    sleepStubs.reset();
    batteryStubs.reset();
    otaStubs.reset();
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

// Fill one PageResponse field from a stub input, leaving it alone when the
// input is empty, the way an absent header does.
static void setField(char* out, size_t size, const char* value) {
    if (!value || !value[0]) return;
    strncpy(out, value, size - 1);
    out[size - 1] = '\0';
}

uint8_t* downloadFile(const char* url, const char* userAgent, int32_t* size,
                      PageResponse* rsp) {
    netStubs.downloadCallCount++;
    netStubs.lastDownloadURL = url;
    netStubs.lastUserAgent = userAgent;
    if (netStubs.downloadBuf != nullptr) {
        *size = netStubs.downloadBufLen;
        if (rsp) {
            rsp->nextRefreshSeconds = netStubs.downloadNextRefresh;
            setField(rsp->nextURL, sizeof(rsp->nextURL), netStubs.downloadNextURL);
            setField(rsp->firmwareVersion, sizeof(rsp->firmwareVersion),
                     netStubs.firmwareVersion);
            setField(rsp->firmwareURL, sizeof(rsp->firmwareURL), netStubs.firmwareURL);
        }
    }
    return netStubs.downloadBuf;
}

// ---------------------------------------------------------------------------
// ota stubs. updateOffered() is pure and is compiled, not stubbed.
// ---------------------------------------------------------------------------
bool otaTrialPending() { return otaStubs.trialPending; }

void otaConfirm() {
    otaStubs.confirmCalled = true;
    otaStubs.trialPending = false;
}

void otaRollback(const char* why) {
    otaStubs.rollbackCalled = true;
    otaStubs.lastRollbackReason = why;
}

const char* otaRejectedVersion() { return otaStubs.rejectedVersion; }

esp_err_t applyFirmwareUpdate(const char* url, const char* version, const char*) {
    otaStubs.applyCallCount++;
    otaStubs.lastApplyURL = url;
    otaStubs.lastApplyVersion = version;
    otaStubs.wifiOffAtApply = WiFi.disconnectCount > 0;
    return ESP_FAIL;   // on-device this restarts and never returns
}

// ---------------------------------------------------------------------------
// settings stub: the config the test image was "flashed" with
// ---------------------------------------------------------------------------
ClientConfig loadConfig() {
    return ClientConfig{
        serverURL, serverRetries, serverDefaultRefreshSeconds,
        wifiSSID, wifiPass, wifiRetries,
        ntpHost, ntpTimezone,
        mqttLoggerEnabled, mqttLoggerBroker, mqttLoggerPort,
        mqttLoggerClientID, mqttLoggerTopic, mqttLoggerRetries,
    };
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

bool startImageCache() { return true; }

bool saveImageCache(const uint8_t*, int32_t) {
    dispStubs.saveImageCacheCalled = true;
    return dispStubs.saveImageCacheResult;
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
