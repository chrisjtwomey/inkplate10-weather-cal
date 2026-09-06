// Host tests for what this project draws over a page: the battery indicator.
//
// The icon is chosen by percentage, and there is a second set for drawing on
// a dark banner. Neither the artwork nor the placement is checked, only which
// of the four bitmaps is handed to the board, because that is the decision
// the code makes and the rest is a matter of taste.
//
// Run with:  pio test -e native_panel

#include <unity.h>

#include "MockBoard.h"
#include "epd.h"
#include "panel.h"

static MockBoard mockBoard;

void setUp() {
    mockBoard = MockBoard();
    epdBegin(mockBoard);
}

void tearDown() {}

// The bitmap displayBatteryStatus() hands to the board, or null if it drew none.
static uint8_t* iconFor(int percent, bool invert) {
    mockBoard = MockBoard();
    epdBegin(mockBoard);
    mockBoard.drawBitmapBuf = nullptr;
    displayBatteryStatus(percent, invert);
    return mockBoard.drawBitmapBuf;
}

// ── An icon is drawn at every level ──────────────────────────────────────

void test_an_icon_is_drawn_when_full() {
    TEST_ASSERT_NOT_NULL(iconFor(100, false));
    TEST_ASSERT_NOT_NULL(iconFor(80, false));
    TEST_ASSERT_NOT_NULL(iconFor(67, false));
}

void test_an_icon_is_drawn_when_half() {
    TEST_ASSERT_NOT_NULL(iconFor(66, false));
    TEST_ASSERT_NOT_NULL(iconFor(50, false));
    TEST_ASSERT_NOT_NULL(iconFor(34, false));
}

void test_an_icon_is_drawn_when_low() {
    TEST_ASSERT_NOT_NULL(iconFor(33, false));
    TEST_ASSERT_NOT_NULL(iconFor(20, false));
    TEST_ASSERT_NOT_NULL(iconFor(11, false));
}

void test_an_icon_is_drawn_when_empty() {
    TEST_ASSERT_NOT_NULL(iconFor(10, false));
    TEST_ASSERT_NOT_NULL(iconFor(5, false));
    TEST_ASSERT_NOT_NULL(iconFor(0, false));
}

// ── The icon changes at each threshold ───────────────────────────────────

void test_the_icon_changes_at_66_percent() {
    TEST_ASSERT_NOT_EQUAL(iconFor(67, false), iconFor(66, false));
}

void test_the_icon_changes_at_33_percent() {
    TEST_ASSERT_NOT_EQUAL(iconFor(34, false), iconFor(33, false));
}

void test_the_icon_changes_at_10_percent() {
    TEST_ASSERT_NOT_EQUAL(iconFor(11, false), iconFor(10, false));
}

// ── Drawing over a dark banner uses the other set ────────────────────────

void test_inverted_uses_a_different_bitmap() {
    uint8_t* normal = iconFor(80, false);
    uint8_t* inverted = iconFor(80, true);
    TEST_ASSERT_NOT_NULL(normal);
    TEST_ASSERT_NOT_NULL(inverted);
    TEST_ASSERT_NOT_EQUAL(normal, inverted);
}

int main(int argc, char** argv) {
    (void)argc;
    (void)argv;
    UNITY_BEGIN();

    RUN_TEST(test_an_icon_is_drawn_when_full);
    RUN_TEST(test_an_icon_is_drawn_when_half);
    RUN_TEST(test_an_icon_is_drawn_when_low);
    RUN_TEST(test_an_icon_is_drawn_when_empty);

    RUN_TEST(test_the_icon_changes_at_66_percent);
    RUN_TEST(test_the_icon_changes_at_33_percent);
    RUN_TEST(test_the_icon_changes_at_10_percent);

    RUN_TEST(test_inverted_uses_a_different_bitmap);

    return UNITY_END();
}
