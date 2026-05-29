// Controllable stub state for the native_integration test environment.
//
// Each struct groups the configuration inputs ("what should this call return?")
// and observation outputs ("was this called, with what args?") for one
// subsystem. Tests configure the inputs in setUp(), call run_app(), then
// assert on the outputs.
//
// All stubs are defined in stubs.cpp; this header just declares them.

#pragma once
#include "error_utils.h"
#include <stdint.h>
#include <stddef.h>
#include <time.h>

// ---------------------------------------------------------------------------
// Network stubs  (configureWiFi / configureTime / configureMQTT / downloadFile)
// ---------------------------------------------------------------------------
struct NetworkStubs {
    // --- inputs ---
    esp_err_t wifiResult = ESP_OK;
    esp_err_t timeResult = ESP_OK;
    esp_err_t mqttResult = ESP_OK;

    // downloadFile: return nullptr to simulate failure, or set downloadBuf to
    // a valid pointer to simulate success.
    uint8_t*    downloadBuf         = nullptr;
    int32_t     downloadBufLen      = 0;
    uint32_t    downloadNextRefresh = 3600; // written to *nextRefreshSeconds
    const char* downloadNextURL     = "";   // written to nextURL buffer

    // --- observations ---
    int         downloadCallCount = 0;
    const char* lastDownloadURL   = nullptr;

    void reset() {
        wifiResult = ESP_OK;
        timeResult = ESP_OK;
        mqttResult = ESP_OK;
        downloadBuf = nullptr;
        downloadBufLen = 0;
        downloadNextRefresh = 3600;
        downloadNextURL = "";
        downloadCallCount = 0;
        lastDownloadURL = nullptr;
    }
};
extern NetworkStubs netStubs;

// ---------------------------------------------------------------------------
// Display stubs (loadImage / displayBatteryStatus / displayMessage /
//                saveCalendarCache)
// ---------------------------------------------------------------------------
struct DisplayStubs {
    // --- inputs ---
    esp_err_t loadImageResult         = ESP_OK;
    bool      saveCalendarCacheResult = true;

    // --- observations ---
    bool        displayMessageCalled    = false;
    const char* lastDisplayMsg          = nullptr;
    int         displayBatteryCallCount = 0;
    int         lastBatteryPercent      = -1;
    bool        lastBatteryInvert       = false;
    int         loadImageCallCount      = 0;
    bool        saveCalendarCacheCalled = false;

    void reset() {
        loadImageResult = ESP_OK;
        saveCalendarCacheResult = true;
        displayMessageCalled = false;
        lastDisplayMsg = nullptr;
        displayBatteryCallCount = 0;
        lastBatteryPercent = -1;
        lastBatteryInvert = false;
        loadImageCallCount = 0;
        saveCalendarCacheCalled = false;
    }
};
extern DisplayStubs dispStubs;

// ---------------------------------------------------------------------------
// Sleep stubs  (sleep_for / sleep / deepSleep)
// ---------------------------------------------------------------------------
struct SleepStubs {
    // --- observations ---
    bool     sleepForCalled   = false;
    uint32_t lastSleepForSecs = 0;
    bool     sleepCalled      = false;
    time_t   lastSleepEpoch   = 0;

    void reset() {
        sleepForCalled = false;
        lastSleepForSecs = 0;
        sleepCalled = false;
        lastSleepEpoch = 0;
    }
};
extern SleepStubs sleepStubs;

// ---------------------------------------------------------------------------
// Battery stub  (getBatteryCapacity)
// ---------------------------------------------------------------------------
struct BatteryStubs {
    // --- inputs ---
    int capacity = 75; // percent returned for any voltage

    void reset() { capacity = 75; }
};
extern BatteryStubs batteryStubs;

// Reset all stub state to defaults (call in test setUp()).
void resetAllStubs();
