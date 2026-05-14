// Native tests for X-Next-Refresh-Seconds header parsing.
//
// parseRefreshTime() reads the server's integer seconds-until-next-refresh
// from the header value. The server is the authority on *when* the next
// refresh should happen; the client just counts down. Strict validation
// keeps a malformed header from setting a bogus wake time.

#include <unity.h>
#include <stdint.h>
#include "refresh_header.h"


static uint32_t out;

void setUp(void) {
    out = 0xDEADBEEF;  // sentinel — unchanged on failure
}

// ---------- success cases ----------

void test_valid_six_hours(void) {
    TEST_ASSERT_TRUE(parseRefreshTime("21600", &out));
    TEST_ASSERT_EQUAL_UINT32(21600, out);
}

void test_valid_one_day(void) {
    TEST_ASSERT_TRUE(parseRefreshTime("86400", &out));
    TEST_ASSERT_EQUAL_UINT32(86400, out);
}

void test_valid_zero(void) {
    // Server might send 0 if the refresh time is "right now" — refresh immediately.
    TEST_ASSERT_TRUE(parseRefreshTime("0", &out));
    TEST_ASSERT_EQUAL_UINT32(0, out);
}

void test_valid_uint32_max(void) {
    TEST_ASSERT_TRUE(parseRefreshTime("4294967295", &out));
    TEST_ASSERT_EQUAL_UINT32(4294967295u, out);
}

// ---------- rejection cases — sentinel must remain ----------

void test_rejects_null_header(void) {
    TEST_ASSERT_FALSE(parseRefreshTime(NULL, &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_null_out(void) {
    TEST_ASSERT_FALSE(parseRefreshTime("21600", NULL));
}

void test_rejects_empty_string(void) {
    TEST_ASSERT_FALSE(parseRefreshTime("", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_non_numeric(void) {
    TEST_ASSERT_FALSE(parseRefreshTime("abc", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_decimal(void) {
    TEST_ASSERT_FALSE(parseRefreshTime("21600.5", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_negative_sign(void) {
    TEST_ASSERT_FALSE(parseRefreshTime("-1", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_old_hhmmss_format(void) {
    // The original header was "09:00:00". If a stale server-client mix sends
    // that, we want a hard failure (not a silent truncation to 9 like the
    // original bug). The colon character must reject.
    TEST_ASSERT_FALSE(parseRefreshTime("09:00:00", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_overflow(void) {
    // 2^32 = 4294967296 → one above uint32 max.
    TEST_ASSERT_FALSE(parseRefreshTime("4294967296", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}

void test_rejects_trailing_whitespace(void) {
    TEST_ASSERT_FALSE(parseRefreshTime("21600 ", &out));
    TEST_ASSERT_EQUAL_UINT32(0xDEADBEEF, out);
}


int main(int argc, char **argv) {
    (void)argc; (void)argv;
    UNITY_BEGIN();
    RUN_TEST(test_valid_six_hours);
    RUN_TEST(test_valid_one_day);
    RUN_TEST(test_valid_zero);
    RUN_TEST(test_valid_uint32_max);
    RUN_TEST(test_rejects_null_header);
    RUN_TEST(test_rejects_null_out);
    RUN_TEST(test_rejects_empty_string);
    RUN_TEST(test_rejects_non_numeric);
    RUN_TEST(test_rejects_decimal);
    RUN_TEST(test_rejects_negative_sign);
    RUN_TEST(test_rejects_old_hhmmss_format);
    RUN_TEST(test_rejects_overflow);
    RUN_TEST(test_rejects_trailing_whitespace);
    return UNITY_END();
}
