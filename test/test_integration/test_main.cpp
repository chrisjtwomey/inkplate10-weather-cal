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
#include "version.h"
#include "time_utils.h"      // SECONDS_IN_DAY / SECONDS_IN_YEAR macros
#include "integration_stubs.h"
#include "WiFi.h"

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
    WiFi.disconnectCount = 0;
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

void test_happy_path_prints_the_running_version_on_the_page() {
    happyPathStubs();

    run_app();

    // Drawn in the same overlay as the battery, so it lands on the page
    // itself rather than on an error banner.
    TEST_ASSERT_TRUE(dispStubs.clientVersionDrawn);
}

void test_happy_path_calls_board_display() {
    happyPathStubs();

    run_app();

    TEST_ASSERT_GREATER_THAN(0, mockBoard.displayCount);
}

void test_happy_path_saves_image_cache() {
    happyPathStubs();

    run_app();

    TEST_ASSERT_TRUE(dispStubs.saveImageCacheCalled);
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

void test_download_sends_the_client_user_agent() {
    happyPathStubs();

    run_app();

    // Neither CLIENT_NAME nor CLIENT_VERSION is set in this build, so the
    // defaults apply; the board name is MockBoard's.
    TEST_ASSERT_EQUAL_STRING("EpdClient/dev (MockBoard)", netStubs.lastUserAgent);
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
    TEST_ASSERT_TRUE(dispStubs.saveImageCacheCalled);
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
    TEST_ASSERT_FALSE(dispStubs.saveImageCacheCalled);
}

// ---------------------------------------------------------------------------
// Cache save failure: non-fatal — app must still sleep for the refresh time
// ---------------------------------------------------------------------------

void test_cache_save_failure_still_sleeps_for_refresh_seconds() {
    happyPathStubs();
    netStubs.downloadNextRefresh      = 1800;
    dispStubs.saveImageCacheResult = false;

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
// Firmware updates
// ---------------------------------------------------------------------------

// The version this test binary reports; CLIENT_VERSION is unset in the
// library's own build, so it is the header's default.
static const char* kRunningVersion = "dev";

static void offerUpdate(const char* version = "v1.6.0") {
    netStubs.firmwareVersion = version;
    netStubs.firmwareURL = "http://test.local:8080/firmware.bin";
}

void test_an_offered_update_is_applied_after_the_page_is_drawn() {
    happyPathStubs();
    offerUpdate();

    run_app();

    TEST_ASSERT_EQUAL_INT(1, otaStubs.applyCallCount);
    TEST_ASSERT_EQUAL_STRING("http://test.local:8080/firmware.bin", otaStubs.lastApplyURL);
    TEST_ASSERT_EQUAL_STRING("v1.6.0", otaStubs.lastApplyVersion);
    // The panel was updated first, and the wake still ends in a sleep.
    TEST_ASSERT_EQUAL_INT(1, mockBoard.displayCount);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

void test_the_radio_is_still_on_when_the_update_is_fetched() {
    // The image is fetched over the network, so the wake cannot turn the
    // radio off until the update step has had its turn.
    happyPathStubs();
    offerUpdate();

    run_app();

    TEST_ASSERT_EQUAL_INT(1, otaStubs.applyCallCount);
    TEST_ASSERT_FALSE(otaStubs.wifiOffAtApply);
    TEST_ASSERT_EQUAL_INT(1, WiFi.disconnectCount);   // off by the end
}

void test_the_running_version_is_not_applied_again() {
    happyPathStubs();
    offerUpdate(kRunningVersion);

    run_app();

    TEST_ASSERT_EQUAL_INT(0, otaStubs.applyCallCount);
}

void test_an_image_this_board_rolled_back_from_is_not_taken_again() {
    happyPathStubs();
    offerUpdate("v1.6.0");
    otaStubs.rejectedVersion = "v1.6.0";

    run_app();

    TEST_ASSERT_EQUAL_INT(0, otaStubs.applyCallCount);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

void test_no_firmware_headers_means_no_update() {
    happyPathStubs();

    run_app();

    TEST_ASSERT_EQUAL_INT(0, otaStubs.applyCallCount);
    TEST_ASSERT_FALSE(otaStubs.confirmCalled);
}

void test_an_update_waits_while_the_battery_is_low() {
    happyPathStubs();
    offerUpdate();
    batteryStubs.capacity = 19;

    run_app();

    TEST_ASSERT_EQUAL_INT(0, otaStubs.applyCallCount);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

void test_an_update_is_applied_at_twenty_percent() {
    happyPathStubs();
    offerUpdate();
    batteryStubs.capacity = 20;

    run_app();

    TEST_ASSERT_EQUAL_INT(1, otaStubs.applyCallCount);
}

void test_a_failed_update_leaves_the_wake_to_end_as_it_would() {
    // The stub returns ESP_FAIL, as applyFirmwareUpdate does when the image
    // did not arrive; on-device a success never returns.
    happyPathStubs();
    offerUpdate();

    run_app();

    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
    TEST_ASSERT_EQUAL_UINT32(3600, sleepStubs.lastSleepForSecs);
    TEST_ASSERT_EQUAL(0, serverBackoffStep);
}

// ---------------------------------------------------------------------------
// Trial boots: the first boot of a freshly written image
// ---------------------------------------------------------------------------

void test_a_trial_boot_that_draws_a_page_is_confirmed() {
    happyPathStubs();
    otaStubs.trialPending = true;

    run_app();

    TEST_ASSERT_TRUE(otaStubs.confirmCalled);
    TEST_ASSERT_FALSE(otaStubs.rollbackCalled);
    TEST_ASSERT_TRUE(sleepStubs.sleepForCalled);
}

void test_a_trial_boot_that_cannot_download_rolls_back() {
    otaStubs.trialPending = true;
    netStubs.downloadBuf = nullptr;

    run_app();

    TEST_ASSERT_TRUE(otaStubs.rollbackCalled);
    TEST_ASSERT_EQUAL_STRING("file download error", otaStubs.lastRollbackReason);
    // Rolling back replaces the back-off sleep; the board reboots instead.
    TEST_ASSERT_FALSE(sleepStubs.sleepForCalled);
}

void test_a_trial_boot_that_cannot_reach_wifi_rolls_back() {
    otaStubs.trialPending = true;
    netStubs.wifiResult = ESP_ERR_TIMEOUT;

    run_app();

    TEST_ASSERT_TRUE(otaStubs.rollbackCalled);
    TEST_ASSERT_FALSE(sleepStubs.sleepCalled);
}

void test_a_trial_boot_that_cannot_draw_rolls_back() {
    happyPathStubs();
    otaStubs.trialPending = true;
    dispStubs.loadImageResult = ESP_FAIL;

    run_app();

    TEST_ASSERT_TRUE(otaStubs.rollbackCalled);
    TEST_ASSERT_EQUAL_STRING("image load error", otaStubs.lastRollbackReason);
    TEST_ASSERT_FALSE(sleepStubs.sleepForCalled);
}

void test_a_normal_boot_confirms_nothing() {
    happyPathStubs();

    run_app();

    TEST_ASSERT_FALSE(otaStubs.confirmCalled);
    TEST_ASSERT_FALSE(otaStubs.rollbackCalled);
}

// ---------------------------------------------------------------------------
// Test runner
// ---------------------------------------------------------------------------

int main(int argc, char** argv) {
    UNITY_BEGIN();

    // Happy path
    RUN_TEST(test_happy_path_sleeps_for_server_refresh_seconds);
    RUN_TEST(test_happy_path_displays_battery_status);
    RUN_TEST(test_happy_path_prints_the_running_version_on_the_page);
    RUN_TEST(test_happy_path_calls_board_display);
    RUN_TEST(test_happy_path_saves_image_cache);
    RUN_TEST(test_happy_path_resets_backoff_step);

    // URL routing
    RUN_TEST(test_first_boot_downloads_from_default_server_url);
    RUN_TEST(test_subsequent_boot_uses_server_provided_next_url);
    RUN_TEST(test_download_sends_the_client_user_agent);
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

    // Firmware updates
    RUN_TEST(test_an_offered_update_is_applied_after_the_page_is_drawn);
    RUN_TEST(test_the_radio_is_still_on_when_the_update_is_fetched);
    RUN_TEST(test_the_running_version_is_not_applied_again);
    RUN_TEST(test_no_firmware_headers_means_no_update);
    RUN_TEST(test_an_image_this_board_rolled_back_from_is_not_taken_again);
    RUN_TEST(test_an_update_waits_while_the_battery_is_low);
    RUN_TEST(test_an_update_is_applied_at_twenty_percent);
    RUN_TEST(test_a_failed_update_leaves_the_wake_to_end_as_it_would);

    // Trial boots
    RUN_TEST(test_a_trial_boot_that_draws_a_page_is_confirmed);
    RUN_TEST(test_a_trial_boot_that_cannot_download_rolls_back);
    RUN_TEST(test_a_trial_boot_that_cannot_reach_wifi_rolls_back);
    RUN_TEST(test_a_trial_boot_that_cannot_draw_rolls_back);
    RUN_TEST(test_a_normal_boot_confirms_nothing);

    return UNITY_END();
}

#endif // NATIVE
