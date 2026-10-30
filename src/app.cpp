// The order of one wake, and every decision about how it ends.
//
// Each step is a call into the library, which holds no policy of its own: it
// does not know how many times to try, what a flat battery means, or when to
// give up on a new image. Those answers live here.
//
// IMPORTANT: every call to sleepUntil() / sleepFor() is followed by an explicit
// return. On-device those calls never return (esp_deep_sleep_start() is
// terminal); the return is unreachable in production but allows test stubs to
// return normally so post-sleep state can be inspected.

#include <WiFi.h>

#include "epd.h"
#include "app.h"
#include "backoff.h"
#include "image.h"
#include "panel.h"
#include "error_utils.h"
#include "log_utils.h"
#include "network_utils.h"
#include "ota.h"
#include "sd_config.h"
#include "settings.h"
#include "sleep_utils.h"
#include "wake.h"
#include "user_agent.h"
#include "version.h"

// Portrait: the pages this client draws are taller than they are wide.
#define PANEL_ROTATION 1
// At or below this the board shows that the battery is critical, and only
// checks the battery until it is above BATTERY_LOW_PERCENT.
#define BATTERY_CRITICAL_PERCENT 5
// How often a board at critical battery wakes to see whether it was charged.
#define BATTERY_CHECK_SECONDS 3600
// Below this the log says so, and the wake carries on.
#define BATTERY_LOW_PERCENT 10
// Below this a firmware update waits for a charge.
#define BATTERY_FOR_UPDATE_PERCENT 20
// The longest wait between tries at WiFi. The back-off's own cap of a day would
// leave the page that old after the network comes back.
#define WIFI_RETRY_MAX_SECONDS 3600

#if defined(TIMING_LOG)
// When each step of a wake ended, in ms since boot. The radio is off before
// the wake ends, so the line goes out at the next wake, once the broker is
// connected.
static char timings[256];
RTC_DATA_ATTR char lastWakeTimings[256];
static void markStep(const char* step) {
    const size_t used = strlen(timings);
    snprintf(timings + used, sizeof(timings) - used, "%s%s %lu", used ? ", " : "", step,
             (unsigned long)millis());
}
static void keepTimings() { snprintf(lastWakeTimings, sizeof(lastWakeTimings), "%s", timings); }
static void logLastWakeTimings() {
    if (!lastWakeTimings[0]) return;
    logf(LOG_INFO, "timing of the last wake (ms since boot): %s", lastWakeTimings);
    lastWakeTimings[0] = '\0';
}
#else
static void markStep(const char*) {}
static void keepTimings() {}
static void logLastWakeTimings() {}
#endif

// How long the radio stays on after the last line it must carry: a line just
// logged is still queued for the broker, and turning the radio off drops it.
#define LOG_DRAIN_MS 100

// Whether this wake has turned the radio off yet.
static bool radioOn;

// Off for the rest of the wake.
static void radioOff() {
    if (!radioOn) return;
#if !defined(NATIVE)
    delay(LOG_DRAIN_MS);
#endif
    WiFi.disconnect();
    WiFi.mode(WIFI_OFF);
    radioOn = false;
}

// The sleep after a page, from the server's answer. A test build sets
// MAX_SLEEP_SECONDS to wake more often than the server's schedule.
static uint32_t sleepAfterPage(uint32_t fromServer) {
#if defined(MAX_SLEEP_SECONDS)
    return fromServer < MAX_SLEEP_SECONDS ? fromServer : MAX_SLEEP_SECONDS;
#else
    return fromServer;
#endif
}

// RTC_DATA_ATTR marks variables that survive deep-sleep cycles on ESP32.
// On the host (NATIVE) they are plain globals.
RTC_DATA_ATTR int bootCount = 0;
// Seconds-until-next-refresh as dictated by the server's
// Next-Display-Refresh-Seconds header. Zero-init on cold boot; preserved across
// deep-sleep cycles. When 0, falls back to the config's refresh seconds.
RTC_DATA_ATTR uint32_t nextRefreshSeconds;
// Exponential back-off step. Incremented on each failed boot (download or
// draw). Reset to 0 on full success. Zero-init on cold reset.
RTC_DATA_ATTR int serverBackoffStep;
// Next URL to fetch as directed by the server's Next-URL header.
// Empty string on cold boot -> falls back to the config's server URL.
RTC_DATA_ATTR char nextServerURL[256];
// Failed tries at WiFi in a row. Zero-init on cold reset.
RTC_DATA_ATTR int wifiBackoffStep;
// Set once the panel shows that the battery is critical. The board then waits
// for BATTERY_LOW_PERCENT, not BATTERY_CRITICAL_PERCENT: a cell's voltage
// creeps up at rest, and each time it crossed back the panel would redraw.
RTC_DATA_ATTR bool batteryCritical;

#ifdef NATIVE
void reset_app_state() {
    bootCount = 0;
    batteryCritical = false;
    wifiBackoffStep = 0;
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
    sleepFor(computeBackoffSeconds(serverBackoffStep));
}

void run_app() {
    ++bootCount;
    radioOn = true;

    startBoard(PANEL_ROTATION);
    startPageCache();
    markStep("board");
    logf(LOG_NOTICE, "##### %s boot #%d #####", epdBoard().deviceName(), bootCount);
    logf(LOG_NOTICE, "############ Client version: %s ############", CLIENT_VERSION);
    logf(LOG_INFO, "User-Agent: %s", clientUserAgent(epdBoard().deviceName()));

    // A freshly written image is on trial: the bootloader takes it back
    // unless this boot draws a page. Every exit below settles that.
    const bool trialBoot = otaTrialPending();
    if (trialBoot) logf(LOG_NOTICE, "trial boot of %s", CLIENT_VERSION);

    logWakeReason();

    const int batteryPercent = readBatteryPercent();
    markStep("battery");

    if (batteryCritical && batteryPercent <= BATTERY_LOW_PERCENT) {
        logf(LOG_INFO, "battery at %d%%, still waiting for a charge", batteryPercent);
        sleepFor(BATTERY_CHECK_SECONDS);
        return;  // terminal
    }
    if (batteryCritical) log(LOG_NOTICE, "battery charged");
    batteryCritical = false;

    ClientConfig cfg = loadConfig(builtInSettings());
    applySdConfig(&cfg);
    markStep("settings");

    if (batteryPercent <= BATTERY_CRITICAL_PERCENT) {
        log(LOG_NOTICE, "battery critical! - checking hourly until charged");
        displayMessage("Battery critical, please charge!", batteryPercent);
        batteryCritical = true;
        sleepFor(BATTERY_CHECK_SECONDS);
        return;  // terminal
    }
    if (batteryPercent <= BATTERY_LOW_PERCENT) log(LOG_WARNING, "battery low, charge soon!");

    if (connectNetwork(cfg) == ESP_ERR_TIMEOUT) {
        const char* errMsg = "wifi connect timeout";
        log(LOG_ERROR, errMsg);
        if (wifiBackoffStep == 0) displayMessage(errMsg, batteryPercent);
        if (trialBoot) {
            otaRollback(errMsg);
            return;  // terminal
        }
        const uint32_t wait = computeBackoffSeconds(wifiBackoffStep++);
        sleepFor(wait < WIFI_RETRY_MAX_SECONDS ? wait : WIFI_RETRY_MAX_SECONDS);
        return;  // terminal
    }
    wifiBackoffStep = 0;

    markStep("network");
    logLastWakeTimings();

    const char* errMsg = nullptr;
    PageFetch page = {};
    page.length = epdBoard().getWidth() * epdBoard().getHeight() * 8 + 100;

    const char* fetchURL = nextServerURL[0] ? nextServerURL : cfg.serverURL;
    if (!fetchPage(fetchURL, clientUserAgent(epdBoard().deviceName()), cfg.serverRetries, &page,
                   &errMsg)) {
        endFailedWake(errMsg, batteryPercent, trialBoot);
        return;  // terminal
    }

    markStep("fetch");

    // What the server said this time replaces what it said last time;
    // silence keeps the previous answer, which survives deep sleep.
    if (page.response.nextRefreshSeconds > 0) nextRefreshSeconds = page.response.nextRefreshSeconds;
    if (page.response.nextURL[0] != '\0')
        snprintf(nextServerURL, sizeof(nextServerURL), "%s", page.response.nextURL);
    logf(LOG_INFO, "next refresh in %u seconds",
         nextRefreshSeconds ? nextRefreshSeconds : cfg.defaultRefreshSeconds);

    // The panel's refresh is most of a wake. Unless an update needs the
    // network after it, the radio goes off before it: after the decode, so
    // a page that will not decode still reaches the log.
    const bool updateOffered = page.response.firmwareVersion[0] != '\0';
    const auto indicators = [batteryPercent, updateOffered] {
        displayBatteryStatus(batteryPercent, false);
        drawClientVersion();
        markStep("decode");
        if (!updateOffered) radioOff();
    };
    if (!drawPage(page, nullptr, cfg.serverRetries, indicators, &errMsg)) {
        endFailedWake(errMsg, batteryPercent, trialBoot);
        return;  // terminal
    }

    markStep("draw");

    // Cache the drawn image so displayMessage can overlay it as a backdrop.
    if (savePageCache(page.data, page.length))
        log(LOG_DEBUG, "page cache saved");
    else
        log(LOG_WARNING, "page cache not saved");

    markStep("cache");

    // A page is on the panel, so this image works. Say so before anything
    // else: the bootloader takes back an unconfirmed image, and a write to
    // the idle slot is refused while one is pending.
    if (trialBoot) otaConfirm();

    // Still on the network, because this is what needs it most.
    beginUpdateProgress(page.response.firmwareVersion);
    takeOfferedUpdate(page.response, clientUserAgent(epdBoard().deviceName()), batteryPercent,
                      BATTERY_FOR_UPDATE_PERCENT, showUpdateProgress);
    endUpdateProgress(batteryPercent);
    markStep("update");

    if (radioOn) log(LOG_NOTICE, "disconnecting WiFi radio...");
    radioOff();

    if (nextRefreshSeconds == 0) {
        // An image, but no word on when to come back. Treat it as a fault.
        endFailedWake("no refresh schedule from server", batteryPercent, trialBoot);
        return;  // terminal
    }

    serverBackoffStep = 0;
    markStep("sleep");
    keepTimings();
    sleepFor(sleepAfterPage(nextRefreshSeconds));
    return;  // terminal
}
