// Native host tests for display_utils and sleep_utils using MockBoard.
//
// Tests verify:
//   - sleep_for() programs the RTC alarm relative to the current epoch.
//   - displayBatteryStatus() selects the correct battery icon bitmap by
//     percentage threshold (both normal and inverted variants).
//
// Run with:  pio test -e native_mock

#include <unity.h>
#include "MockBoard.h"
#include "display_utils.h"
#include "sleep_utils.h"

// ---------------------------------------------------------------------------
// Board instance shared by all modules under test.
// display_utils.cpp and sleep_utils.cpp both declare:  extern IBoard& board;
// We satisfy that declaration here.
// ---------------------------------------------------------------------------
static MockBoard mockBoard;
IBoard& board = mockBoard;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
static void resetMock() {
    mockBoard = MockBoard();
}

// Call displayBatteryStatus and return the buf pointer passed to drawBitmap.
static uint8_t* iconBufFor(int percent, bool invert) {
    resetMock();
    mockBoard.drawBitmapBuf = nullptr;
    displayBatteryStatus(percent, invert);
    return mockBoard.drawBitmapBuf;
}

// ---------------------------------------------------------------------------
// setUp / tearDown (called by Unity before/after each test)
// ---------------------------------------------------------------------------
void setUp()    { resetMock(); }
void tearDown() {}

// ---------------------------------------------------------------------------
// sleep_for tests
// ---------------------------------------------------------------------------

void test_sleep_for_sets_rtc_alarm_relative_to_epoch() {
    mockBoard.epochReturn = 1000;
    sleep_for(3600);
    TEST_ASSERT_TRUE(mockBoard.rtcSetAlarmEpochCalled);
    TEST_ASSERT_EQUAL(4600, mockBoard.lastAlarmEpoch);
}

void test_sleep_for_zero_seconds() {
    mockBoard.epochReturn = 500;
    sleep_for(0);
    TEST_ASSERT_EQUAL(500, mockBoard.lastAlarmEpoch);
}

void test_sleep_for_large_offset() {
    mockBoard.epochReturn = 0;
    sleep_for(86400);   // 24 h
    TEST_ASSERT_EQUAL(86400, mockBoard.lastAlarmEpoch);
}

// ---------------------------------------------------------------------------
// displayBatteryStatus — icon selection tests.
//
// icons_32x32.h defines its bitmaps as `static`, so each translation unit
// gets its own copy. We cannot compare raw pointer values across TUs.
// Instead we verify:
//   1. A bitmap is actually passed to drawBitmap (not null).
//   2. The icon changes at the correct percentage thresholds.
//   3. Normal and inverted variants produce different pointers.
// ---------------------------------------------------------------------------

void test_battery_icon_drawn_for_full() {
    TEST_ASSERT_NOT_NULL(iconBufFor(100, false));
    TEST_ASSERT_NOT_NULL(iconBufFor(80,  false));
    TEST_ASSERT_NOT_NULL(iconBufFor(67,  false));
}

void test_battery_icon_drawn_for_half() {
    TEST_ASSERT_NOT_NULL(iconBufFor(66, false));
    TEST_ASSERT_NOT_NULL(iconBufFor(50, false));
    TEST_ASSERT_NOT_NULL(iconBufFor(34, false));
}

void test_battery_icon_drawn_for_low() {
    TEST_ASSERT_NOT_NULL(iconBufFor(33, false));
    TEST_ASSERT_NOT_NULL(iconBufFor(20, false));
    TEST_ASSERT_NOT_NULL(iconBufFor(11, false));
}

void test_battery_icon_drawn_for_empty() {
    TEST_ASSERT_NOT_NULL(iconBufFor(10, false));
    TEST_ASSERT_NOT_NULL(iconBufFor(5,  false));
    TEST_ASSERT_NOT_NULL(iconBufFor(0,  false));
}

// Icon changes at the 66% threshold (full → half).
void test_battery_icon_changes_at_66_percent() {
    uint8_t* above = iconBufFor(67, false);   // full
    uint8_t* at    = iconBufFor(66, false);   // half
    TEST_ASSERT_NOT_NULL(above);
    TEST_ASSERT_NOT_NULL(at);
    TEST_ASSERT_NOT_EQUAL(above, at);
}

// Icon changes at the 33% threshold (half → low).
void test_battery_icon_changes_at_33_percent() {
    uint8_t* above = iconBufFor(34, false);   // half
    uint8_t* at    = iconBufFor(33, false);   // low
    TEST_ASSERT_NOT_NULL(above);
    TEST_ASSERT_NOT_NULL(at);
    TEST_ASSERT_NOT_EQUAL(above, at);
}

// Icon changes at the 10% threshold (low → empty).
void test_battery_icon_changes_at_10_percent() {
    uint8_t* above = iconBufFor(11, false);   // low
    uint8_t* at    = iconBufFor(10, false);   // empty
    TEST_ASSERT_NOT_NULL(above);
    TEST_ASSERT_NOT_NULL(at);
    TEST_ASSERT_NOT_EQUAL(above, at);
}

// Normal and inverted variants must use different bitmap buffers.
void test_battery_icon_invert_uses_different_bitmap() {
    uint8_t* normal   = iconBufFor(80, false);
    uint8_t* inverted = iconBufFor(80, true);
    TEST_ASSERT_NOT_NULL(normal);
    TEST_ASSERT_NOT_NULL(inverted);
    TEST_ASSERT_NOT_EQUAL(normal, inverted);
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------
int main(int argc, char** argv) {
    (void)argc; (void)argv;
    UNITY_BEGIN();

    // sleep_for
    RUN_TEST(test_sleep_for_sets_rtc_alarm_relative_to_epoch);
    RUN_TEST(test_sleep_for_zero_seconds);
    RUN_TEST(test_sleep_for_large_offset);

    // battery icon — drawn
    RUN_TEST(test_battery_icon_drawn_for_full);
    RUN_TEST(test_battery_icon_drawn_for_half);
    RUN_TEST(test_battery_icon_drawn_for_low);
    RUN_TEST(test_battery_icon_drawn_for_empty);

    // battery icon — threshold transitions
    RUN_TEST(test_battery_icon_changes_at_66_percent);
    RUN_TEST(test_battery_icon_changes_at_33_percent);
    RUN_TEST(test_battery_icon_changes_at_10_percent);

    // battery icon — normal vs inverted
    RUN_TEST(test_battery_icon_invert_uses_different_bitmap);

    return UNITY_END();
}
