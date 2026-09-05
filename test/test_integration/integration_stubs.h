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
    uint32_t    downloadNextRefresh = 3600; // written to rsp->nextRefreshSeconds
    const char* downloadNextURL     = "";   // written to rsp->nextURL
    const char* firmwareVersion     = "";   // written to rsp->firmwareVersion
    const char* firmwareURL         = "";   // written to rsp->firmwareURL

    // --- observations ---
    int         downloadCallCount = 0;
    const char* lastDownloadURL   = nullptr;
    const char* lastUserAgent     = nullptr;

    void reset() {
        wifiResult = ESP_OK;
        timeResult = ESP_OK;
        mqttResult = ESP_OK;
        downloadBuf = nullptr;
        downloadBufLen = 0;
        downloadNextRefresh = 3600;
        downloadNextURL = "";
        firmwareVersion = "";
        firmwareURL = "";
        downloadCallCount = 0;
        lastDownloadURL = nullptr;
        lastUserAgent = nullptr;
    }
};
extern NetworkStubs netStubs;

// ---------------------------------------------------------------------------
// Display stubs (loadImage / displayBatteryStatus / displayMessage /
//                saveImageCache)
// ---------------------------------------------------------------------------
struct DisplayStubs {
    bool clientVersionDrawn;
    // --- inputs ---
    esp_err_t loadImageResult         = ESP_OK;
    bool      saveImageCacheResult = true;

    // --- observations ---
    bool        displayMessageCalled    = false;
    const char* lastDisplayMsg          = nullptr;
    int         displayBatteryCallCount = 0;
    int         lastBatteryPercent      = -1;
    bool        lastBatteryInvert       = false;
    int         loadImageCallCount      = 0;
    bool        saveImageCacheCalled = false;

    void reset() {
        loadImageResult = ESP_OK;
        saveImageCacheResult = true;
        displayMessageCalled = false;
        lastDisplayMsg = nullptr;
        displayBatteryCallCount = 0;
        lastBatteryPercent = -1;
        lastBatteryInvert = false;
        loadImageCallCount = 0;
        saveImageCacheCalled = false;
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
// OTA stubs  (otaTrialPending / otaConfirm / otaRollback / applyFirmwareUpdate)
// ---------------------------------------------------------------------------
struct OtaStubs {
    // --- inputs ---
    bool trialPending = false;      // is this the first boot of a new image?
    const char* rejectedVersion = "";   // what a previous trial rolled back from

    // --- observations ---
    bool        confirmCalled      = false;
    bool        rollbackCalled     = false;
    const char* lastRollbackReason = nullptr;
    int         applyCallCount     = 0;
    const char* lastApplyURL       = nullptr;
    const char* lastApplyVersion   = nullptr;
    bool        wifiOffAtApply     = false;   // had the radio been turned off?

    void reset() {
        trialPending = false;
        rejectedVersion = "";
        confirmCalled = false;
        rollbackCalled = false;
        lastRollbackReason = nullptr;
        applyCallCount = 0;
        lastApplyURL = nullptr;
        lastApplyVersion = nullptr;
        wifiOffAtApply = false;
    }
};
extern OtaStubs otaStubs;

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
