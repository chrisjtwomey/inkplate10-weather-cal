// Stub implementations for all free functions called by app.cpp that are NOT
// compiled in the native_integration environment (network_utils, image,
// sleep_utils, battery, log_utils, time_utils, ota, settings).
//
// Each stub records the call in the corresponding *Stubs struct so tests can
// assert on what was invoked and with what arguments.

#ifdef NATIVE

#include <stdarg.h>
#include <string.h>
#include "integration_stubs.h"

// Pull in headers that declare the functions we are defining.
#include "log_utils.h"        // log(), logf(), configureMQTT()
#include "network_utils.h"    // configureWiFi(), downloadFile()
#include "image.h"
#include "panel.h"            // displayBatteryStatus(), displayMessage()
#include "sleep_utils.h"      // sleepFor(), sleepUntil(), deepSleep()
#include "battery.h"          // batteryPercent()
#include "time_utils.h"       // nowTzFmt(), setClock(), setTimezone()
#include "ota.h"              // otaTrialPending(), otaConfirm(), otaRollback(),
                              // applyFirmwareUpdate()
#include "wake.h"             // the steps run_app() is built from
#include "app.h"              // builtInSettings()
#include "settings.h"         // loadConfig()
#include "WiFi.h"
#include "LittleFS.h"
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
LittleFSClass LittleFS;
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
void setClock(time_t) {}
void setTimezone(const char*) {}
void restoreTimezone() {}

// ---------------------------------------------------------------------------
// battery stub
// ---------------------------------------------------------------------------
int batteryPercent(double) {
    return batteryStubs.percent;
}

// ---------------------------------------------------------------------------
// network_utils stubs
// ---------------------------------------------------------------------------
esp_err_t configureWiFi(const char*, const char*, int) {
    return netStubs.wifiResult;
}

// Fill one ServerResponse field from a stub input, leaving it alone when the
// input is empty, the way an absent header does.
static void setField(char* out, size_t size, const char* value) {
    if (!value || !value[0]) return;
    strncpy(out, value, size - 1);
    out[size - 1] = '\0';
}

uint8_t* downloadFile(const char* url, const char* userAgent, int32_t* size,
                      ServerResponse* rsp) {
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

esp_err_t applyFirmwareUpdate(const char* url, const char* version, const char*,
                              OtaProgress onProgress) {
    otaStubs.applyCallCount++;
    otaStubs.progressHookGiven = onProgress != nullptr;
    otaStubs.lastApplyURL = url;
    otaStubs.lastApplyVersion = version;
    otaStubs.wifiOffAtApply = WiFi.disconnectCount > 0;
    return ESP_FAIL;   // on-device this restarts and never returns
}

// ---------------------------------------------------------------------------
// settings stub: no NVS on the host, so the image's own values stand
// ---------------------------------------------------------------------------
ClientConfig loadConfig(const ClientConfig& compiled) { return compiled; }

// ---------------------------------------------------------------------------
// image stubs
// ---------------------------------------------------------------------------
esp_err_t drawImage(const char*) {
    dispStubs.drawImageCallCount++;
    return dispStubs.drawImageResult;
}

esp_err_t drawImage(const uint8_t*, int32_t) {
    dispStubs.drawImageCallCount++;
    return dispStubs.drawImageResult;
}

void displayBatteryStatus(int percent, bool invert) {
    dispStubs.displayBatteryCallCount++;
    dispStubs.lastBatteryPercent = percent;
    dispStubs.lastBatteryInvert  = invert;
}

void drawClientVersion() { dispStubs.clientVersionDrawn = true; }

void beginUpdateProgress(const char* version) { dispStubs.updateScreenVersion = version; }
void showUpdateProgress(int, int) {}
void endUpdateProgress(int) { dispStubs.updateScreenEnded = true; }

void displayMessage(const char* msg, int) {
    dispStubs.displayMessageCalled = true;
    dispStubs.lastDisplayMsg       = msg;
}

bool startPageCache() { return true; }

bool savePageCache(const uint8_t*, int32_t) {
    dispStubs.savePageCacheCalled = true;
    return dispStubs.savePageCacheResult;
}

// ---------------------------------------------------------------------------
// sleep_utils stubs
// ---------------------------------------------------------------------------
void sleepFor(uint32_t seconds) {
    sleepStubs.sleepForCalled   = true;
    sleepStubs.lastSleepForSecs = seconds;
}

void sleepUntil(time_t epoch) {
    sleepStubs.sleepUntilCalled    = true;
    sleepStubs.lastSleepUntilEpoch = epoch;
}

void deepSleep() {}

#endif // NATIVE
