// The order of one wake, and every decision about how it ends.
//
// Each step is a call into the library, which holds no policy of its own: it
// does not know how many times to try, what a flat battery means, or when to
// give up on a new image. Those answers live here.
//
// IMPORTANT: every call to sleep() / sleep_for() is followed by an explicit
// return. On-device those calls never return (esp_deep_sleep_start() is
// terminal); the return is unreachable in production but allows test stubs to
// return normally so post-sleep state can be inspected.

#include <WiFi.h>

#include "epd.h"
#include "app.h"
#include "backoff.h"
#include "display_utils.h"
#include "panel.h"
#include "error_utils.h"
#include "log_utils.h"
#include "network_utils.h"
#include "ota.h"
#include "sd_config.h"
#include "settings.h"
#include "sleep_utils.h"
#include "wake.h"
#include "time_utils.h"
#include "user_agent.h"
#include "version.h"

#if defined(USE_SDCARD)
#include "file_utils.h"
#endif

// Portrait: the pages this client draws are taller than they are wide.
#define PANEL_ROTATION 1
// Below this the board sleeps until someone charges it.
#define BATTERY_CRITICAL_PERCENT 5
// Below this the log says so, and the wake carries on.
#define BATTERY_LOW_PERCENT 10
// Below this a firmware update waits for a charge.
#define BATTERY_FOR_UPDATE_PERCENT 20
// How long to wait after WiFi did not connect. Short: the network is the
// most likely thing to come back on its own.
#define WIFI_RETRY_SECONDS 60

// RTC_DATA_ATTR marks variables that survive deep-sleep cycles on ESP32.
// On the host (NATIVE) they are plain globals.
RTC_DATA_ATTR int bootCount = 0;
// Seconds-until-next-refresh as dictated by the server's
// X-Next-Refresh-Seconds header. Zero-init on cold boot; preserved across
// deep-sleep cycles. When 0, falls back to the config's refresh seconds.
RTC_DATA_ATTR uint32_t nextRefreshSeconds;
// Exponential back-off step. Incremented on each failed boot (download or
// draw). Reset to 0 on full success. Zero-init on cold reset.
RTC_DATA_ATTR int serverBackoffStep;
// Next URL to fetch as directed by the server's X-Next-URL header.
// Empty string on cold boot -> falls back to the config's server URL.
RTC_DATA_ATTR char nextServerURL[256];

#ifdef NATIVE
void reset_app_state() {
    bootCount = 0;
    nextRefreshSeconds = 0;
    serverBackoffStep = 0;
    nextServerURL[0] = '\0';
}
#endif

// Every failed wake ends the same way: say so on the panel, give up on an
// image that is still on trial, then back off and sleep.
static void endFailedWake(const char* errMsg, int batteryPercent, bool trialBoot) {
    displayMessage(errMsg, batteryPercent);
    if (trialBoot) {
        otaRollback(errMsg);
        return;  // terminal
    }
    serverBackoffStep++;
    logf(LOG_NOTICE, "%s (back-off step %d): sleeping %u s", errMsg, serverBackoffStep,
         computeBackoffSeconds(serverBackoffStep));
    sleep_for(computeBackoffSeconds(serverBackoffStep));
}

void run_app() {
    ++bootCount;

    startBoard(PANEL_ROTATION);
    startImageCache();
    logf(LOG_NOTICE, "##### %s boot #%d #####", epdBoard().deviceName(), bootCount);
    logf(LOG_NOTICE, "############ Client version: %s ############", CLIENT_VERSION);
    logf(LOG_INFO, "User-Agent: %s", clientUserAgent(epdBoard().deviceName()));

    // A freshly written image is on trial: the bootloader takes it back
    // unless this boot draws a page. Every exit below settles that.
    const bool trialBoot = otaTrialPending();
    if (trialBoot) logf(LOG_NOTICE, "trial boot of %s", CLIENT_VERSION);

    logWakeReason();

    const int batteryPercent = readBatteryPercent();

    ClientConfig cfg = loadConfig(compiledDefaults());
    const bool cardPresent = applySdConfig(&cfg);

    if (batteryPercent <= BATTERY_CRITICAL_PERCENT) {
        log(LOG_NOTICE, "battery critical! - sleeping until charged");
        displayMessage("Battery critical, please charge!", batteryPercent);
        sleep(epdBoard().rtcGetEpoch() + SECONDS_IN_YEAR);
        return;  // terminal
    }
    if (batteryPercent <= BATTERY_LOW_PERCENT) log(LOG_WARNING, "battery low, charge soon!");

    if (connectNetwork(cfg) == ESP_ERR_TIMEOUT) {
        const char* errMsg = "wifi connect timeout";
        log(LOG_ERROR, errMsg);
        displayMessage(errMsg, batteryPercent);
        if (trialBoot) {
            otaRollback(errMsg);
            return;  // terminal
        }
        // Not the server's fault, so the back-off step is left alone.
        sleep(epdBoard().rtcGetEpoch() + WIFI_RETRY_SECONDS);
        return;  // terminal
    }

    const char* errMsg = nullptr;
    PageFetch page = {};
    page.length = epdBoard().getWidth() * epdBoard().getHeight() * 8 + 100;

    const char* fetchURL = nextServerURL[0] ? nextServerURL : cfg.serverURL;
    if (!fetchPage(fetchURL, clientUserAgent(epdBoard().deviceName()), cfg.serverRetries, &page,
                   &errMsg)) {
        endFailedWake(errMsg, batteryPercent, trialBoot);
        return;  // terminal
    }

    // What the server said this time replaces what it said last time;
    // silence keeps the previous answer, which survives deep sleep.
    if (page.response.nextRefreshSeconds > 0) nextRefreshSeconds = page.response.nextRefreshSeconds;
    if (page.response.nextURL[0] != '\0')
        snprintf(nextServerURL, sizeof(nextServerURL), "%s", page.response.nextURL);
    logf(LOG_INFO, "next refresh in %u seconds",
         nextRefreshSeconds ? nextRefreshSeconds : cfg.defaultRefreshSeconds);

    const char* imagePath = nullptr;
#if defined(USE_SDCARD)
    // The card holds the image the panel draws from, and keeps it for the
    // next wake. Without one the buffer serves for this wake alone.
    if (cardPresent) {
        if (writeFile(page.data, page.length, IMAGE_RW_PATH) != ESP_OK) {
            endFailedWake("file write error", batteryPercent, trialBoot);
            return;  // terminal
        }
        imagePath = IMAGE_RW_PATH;
    }
#else
    (void)cardPresent;
#endif

    const auto indicators = [batteryPercent] {
        displayBatteryStatus(batteryPercent, false);
        drawClientVersion();
    };
    if (!drawPage(page, imagePath, cfg.serverRetries, indicators, &errMsg)) {
        endFailedWake(errMsg, batteryPercent, trialBoot);
        return;  // terminal
    }

    // Cache the drawn image so displayMessage can overlay it as a backdrop.
    if (saveImageCache(page.data, page.length))
        log(LOG_DEBUG, "image cache saved to SPIFFS");
    else
        log(LOG_WARNING, "failed to save image cache to SPIFFS");

    // A page is on the panel, so this image works. Say so before anything
    // else: the bootloader takes back an unconfirmed image, and a write to
    // the idle slot is refused while one is pending.
    if (trialBoot) otaConfirm();

    // Still on the network, because this is what needs it most.
    takeOfferedUpdate(page.response, clientUserAgent(epdBoard().deviceName()), batteryPercent,
                      BATTERY_FOR_UPDATE_PERCENT);

    log(LOG_NOTICE, "disconnecting WiFi radio...");
    WiFi.disconnect();
    WiFi.mode(WIFI_OFF);

    if (nextRefreshSeconds == 0) {
        // An image, but no word on when to come back. Treat it as a fault.
        endFailedWake("no refresh schedule from server", batteryPercent, trialBoot);
        return;  // terminal
    }

    serverBackoffStep = 0;
    sleep_for(nextRefreshSeconds);
    return;  // terminal
}
