// Integration tests for run_app() — the main firmware control flow.
//
// Each test exercises a complete simulated boot from start to the terminal
// sleep call. The IBoard is a MockBoard; all other collaborators (WiFi,
// download, display, sleep) are replaced by controllable stubs defined in
// stubs.cpp / integration_stubs.h.
//
// Test naming convention: test_<scenario>_<expected outcome>

#ifdef NATIVE

#include <unity.h>
#include <string.h>
#include "MockBoard.h"
#include "IBoard.h"
#include "app.h"
#include "backoff.h"
#include "time_utils.h"      // SECONDS_IN_DAY / SECONDS_IN_YEAR macros
#include "integration_stubs.h"

// ---------------------------------------------------------------------------
// Global board instance (satisfies extern IBoard& board in app.cpp)
// ---------------------------------------------------------------------------
static MockBoard mockBoard;
IBoard& board = mockBoard;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// A minimal byte sequence used as a "downloaded image" in happy-path tests.
// loadImage is stubbed, so the actual content doesn't matter.
static uint8_t kFakePng[] = { 0x89, 0x50, 0x4E, 0x47, 0x00 };
static const int32_t kFakePngLen = (int32_t)sizeof(kFakePng);

static void resetAll() {
    reset_app_state();
    resetAllStubs();
    mockBoard = MockBoard(); // reset all call counters and return values
    // Default wakeup cause: cold boot (power-on reset)
    extern esp_sleep_wakeup_cause_t g_wakeup_cause;
    g_wakeup_cause = ESP_SLEEP_WAKEUP_UNDEFINED;
}

static void happyPathStubs() {
    netStubs.wifiResult         = ESP_OK;
    netStubs.downloadBuf        = kFakePng;
    netStubs.downloadBufLen     = kFakePngLen;
    netStubs.downloadNextRefresh = 3600;
}

// ---------------------------------------------------------------------------
// Test lifecycle
// ---------------------------------------------------------------------------
void setUp()    { resetAll(); }
void tearDown() {}

// ---------------------------------------------------------------------------
// Happy path
// ---------------------------------------------------------------------------

void test_happy_path_sleeps_for_server_refresh_seconds() {
    happyPathStubs();
    netStubs.downloadNextRefresh = 7200;

    run_app();

    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
    TEST_ASSERT_EQUAL_UINT32(7200, sleepStubs.lastSleepForSecs);
    TEST_ASSERT_FALSE(sleepStubs.sleepCalled); // absolute sleep must NOT fire
}

void test_happy_path_displays_battery_status() {
    happyPathStubs();
    batteryStubs.capacity = 55;

    run_app();

    TEST_ASSERT_EQUAL(1, dispStubs.displayBatteryCallCount);
    TEST_ASSERT_EQUAL(55, dispStubs.lastBatteryPercent);
    TEST_ASSERT_FALSE(dispStubs.lastBatteryInvert);
}

void test_happy_path_calls_board_display() {
    happyPathStubs();

    run_app();

    TEST_ASSERT_GREATER_THAN(0, mockBoard.displayCount);
}

void test_happy_path_saves_calendar_cache() {
    happyPathStubs();

    run_app();

    TEST_ASSERT_TRUE(dispStubs.saveCalendarCacheCalled);
}

void test_happy_path_resets_backoff_step() {
    serverBackoffStep = 4; // simulate previous failures
    happyPathStubs();
    netStubs.downloadNextRefresh = 1800;

    run_app();

    TEST_ASSERT_EQUAL(0, serverBackoffStep);
}

// ---------------------------------------------------------------------------
// URL routing
// ---------------------------------------------------------------------------

void test_first_boot_downloads_from_default_server_url() {
    // nextServerURL is empty after reset_app_state()
    happyPathStubs();

    run_app();

    extern char serverURL[];
    TEST_ASSERT_EQUAL_STRING(serverURL, netStubs.lastDownloadURL);
}

void test_subsequent_boot_uses_server_provided_next_url() {
    strncpy(nextServerURL, "http://alt.server/next.png", sizeof(nextServerURL));
    happyPathStubs();

    run_app();

    TEST_ASSERT_EQUAL_STRING("http://alt.server/next.png", netStubs.lastDownloadURL);
}

void test_download_response_persists_next_url_for_next_boot() {
    happyPathStubs();
    netStubs.downloadNextURL = "http://server/scheduled-next.png";

    run_app();

    // nextServerURL is the RTC-persisted buffer — verify the stub's out-param was stored
    TEST_ASSERT_EQUAL_STRING("http://server/scheduled-next.png", nextServerURL);
}

// ---------------------------------------------------------------------------
// WiFi failure
// ---------------------------------------------------------------------------

void test_wifi_timeout_shows_error_and_sleeps_60s_from_epoch() {
    netStubs.wifiResult = ESP_ERR_TIMEOUT;
    mockBoard.epochReturn = 1000;

    run_app();

    TEST_ASSERT_TRUE(dispStubs.displayMessageCalled);
    TEST_ASSERT_TRUE(sleepStubs.sleepCalled);
    TEST_ASSERT_EQUAL((time_t)1060, sleepStubs.lastSleepEpoch);
    // Must not have attempted a download
    TEST_ASSERT_EQUAL(0, netStubs.downloadCallCount);
}

void test_wifi_timeout_does_not_increment_backoff_step() {
    netStubs.wifiResult = ESP_ERR_TIMEOUT;
    // serverBackoffStep starts at 0 (from resetAll())

    run_app();

    // Backoff is reserved for download/draw failures only
    TEST_ASSERT_EQUAL(0, serverBackoffStep);
}

// ---------------------------------------------------------------------------
// Time sync / MQTT: non-fatal network setup failures
// ---------------------------------------------------------------------------

void test_time_sync_failure_still_proceeds_to_download() {
    happyPathStubs();
    netStubs.timeResult = ESP_FAIL;

    run_app();

    TEST_ASSERT_EQUAL(1, netStubs.downloadCallCount);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

void test_mqtt_timeout_still_proceeds_to_download() {
    happyPathStubs();
    netStubs.mqttResult = ESP_ERR_TIMEOUT;

    run_app();

    TEST_ASSERT_EQUAL(1, netStubs.downloadCallCount);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

// ---------------------------------------------------------------------------
// Download failure / backoff
// ---------------------------------------------------------------------------

void test_download_failure_shows_error_and_backs_off() {
    netStubs.wifiResult  = ESP_OK;
    netStubs.downloadBuf = nullptr; // every attempt fails

    run_app();

    TEST_ASSERT_TRUE(dispStubs.displayMessageCalled);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
    // serverBackoffStep was 0, incremented to 1 before the sleep call
    TEST_ASSERT_EQUAL_UINT32(computeBackoffSeconds(1), sleepStubs.lastSleepForSecs);
    TEST_ASSERT_EQUAL(1, serverBackoffStep);
}

void test_download_failure_increments_backoff_step_from_previous() {
    serverBackoffStep    = 2;
    netStubs.wifiResult  = ESP_OK;
    netStubs.downloadBuf = nullptr;

    run_app();

    TEST_ASSERT_EQUAL(3, serverBackoffStep);
    TEST_ASSERT_EQUAL_UINT32(computeBackoffSeconds(3), sleepStubs.lastSleepForSecs);
}

// ---------------------------------------------------------------------------
// No refresh header — server omits X-Next-Refresh-Seconds
// ---------------------------------------------------------------------------

void test_no_refresh_header_backs_off_instead_of_sleeping_zero() {
    happyPathStubs();
    netStubs.downloadNextRefresh = 0; // stub writes 0 → no refresh header

    run_app();

    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
    // nextRefreshSeconds == 0, so app takes the backoff branch
    TEST_ASSERT_EQUAL_UINT32(computeBackoffSeconds(1), sleepStubs.lastSleepForSecs);
    // cache is still saved (image was drawn successfully)
    TEST_ASSERT_TRUE(dispStubs.saveCalendarCacheCalled);
}

// ---------------------------------------------------------------------------
// Battery critical / low
// ---------------------------------------------------------------------------

void test_battery_critical_sleeps_long_without_downloading() {
    batteryStubs.capacity = 3; // 3% — below the ≤5% threshold
    mockBoard.epochReturn  = 500;

    run_app();

    TEST_ASSERT_TRUE(dispStubs.displayMessageCalled);
    TEST_ASSERT_TRUE(sleepStubs.sleepCalled);
    TEST_ASSERT_EQUAL((time_t)(500 + SECONDS_IN_YEAR), sleepStubs.lastSleepEpoch);
    TEST_ASSERT_EQUAL(0, netStubs.downloadCallCount);
}

void test_battery_low_continues_to_download() {
    batteryStubs.capacity = 10; // exactly at the "low" threshold — warn only
    happyPathStubs();

    run_app();

    // Should still attempt to download
    TEST_ASSERT_EQUAL(1, netStubs.downloadCallCount);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

// ---------------------------------------------------------------------------
// Image draw failure
// ---------------------------------------------------------------------------

void test_load_image_failure_backs_off_without_caching() {
    happyPathStubs();
    dispStubs.loadImageResult = ESP_FAIL;

    run_app();

    TEST_ASSERT_TRUE(dispStubs.displayMessageCalled);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
    TEST_ASSERT_EQUAL_UINT32(computeBackoffSeconds(1), sleepStubs.lastSleepForSecs);
    // Cache must NOT be saved when the draw failed
    TEST_ASSERT_FALSE(dispStubs.saveCalendarCacheCalled);
}

// ---------------------------------------------------------------------------
// Cache save failure: non-fatal — app must still sleep for the refresh time
// ---------------------------------------------------------------------------

void test_cache_save_failure_still_sleeps_for_refresh_seconds() {
    happyPathStubs();
    netStubs.downloadNextRefresh      = 1800;
    dispStubs.saveCalendarCacheResult = false;

    run_app();

    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
    TEST_ASSERT_EQUAL_UINT32(1800, sleepStubs.lastSleepForSecs);
}

// ---------------------------------------------------------------------------
// Wakeup cause: EXT0 (RTC alarm) clears the alarm flag
// ---------------------------------------------------------------------------

void test_ext0_wakeup_clears_rtc_alarm_flag() {
    extern esp_sleep_wakeup_cause_t g_wakeup_cause;
    g_wakeup_cause = ESP_SLEEP_WAKEUP_EXT0;
    happyPathStubs();

    run_app();

    TEST_ASSERT_TRUE(mockBoard.rtcClearAlarmFlagCalled);
}

void test_cold_boot_does_not_clear_rtc_alarm_flag() {
    // g_wakeup_cause already == ESP_SLEEP_WAKEUP_UNDEFINED from resetAll()
    happyPathStubs();

    run_app();

    TEST_ASSERT_FALSE(mockBoard.rtcClearAlarmFlagCalled);
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
    UNITY_BEGIN();

    // Happy path
    RUN_TEST(test_happy_path_sleeps_for_server_refresh_seconds);
    RUN_TEST(test_happy_path_displays_battery_status);
    RUN_TEST(test_happy_path_calls_board_display);
    RUN_TEST(test_happy_path_saves_calendar_cache);
    RUN_TEST(test_happy_path_resets_backoff_step);

    // URL routing
    RUN_TEST(test_first_boot_downloads_from_default_server_url);
    RUN_TEST(test_subsequent_boot_uses_server_provided_next_url);
    RUN_TEST(test_download_response_persists_next_url_for_next_boot);

    // WiFi failure
    RUN_TEST(test_wifi_timeout_shows_error_and_sleeps_60s_from_epoch);
    RUN_TEST(test_wifi_timeout_does_not_increment_backoff_step);

    // Time sync / MQTT: non-fatal failures
    RUN_TEST(test_time_sync_failure_still_proceeds_to_download);
    RUN_TEST(test_mqtt_timeout_still_proceeds_to_download);

    // Download failure / backoff
    RUN_TEST(test_download_failure_shows_error_and_backs_off);
    RUN_TEST(test_download_failure_increments_backoff_step_from_previous);

    // No refresh header
    RUN_TEST(test_no_refresh_header_backs_off_instead_of_sleeping_zero);

    // Battery
    RUN_TEST(test_battery_critical_sleeps_long_without_downloading);
    RUN_TEST(test_battery_low_continues_to_download);

    // Draw failure
    RUN_TEST(test_load_image_failure_backs_off_without_caching);

    // Cache save failure
    RUN_TEST(test_cache_save_failure_still_sleeps_for_refresh_seconds);

    // Wakeup cause
    RUN_TEST(test_ext0_wakeup_clears_rtc_alarm_flag);
    RUN_TEST(test_cold_boot_does_not_clear_rtc_alarm_flag);

    return UNITY_END();
}

#endif // NATIVE
