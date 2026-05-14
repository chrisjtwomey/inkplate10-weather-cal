// Native tests for the exponential back-off helper.
//
// computeBackoffSeconds() is pure — no hardware, no globals.
// Sequence: 120s (2min), ×3 each step, capped at 86400s (24h).

#include <unity.h>
#include "backoff.h"


void test_step_0_is_2_minutes(void) {
    TEST_ASSERT_EQUAL_UINT32(120, computeBackoffSeconds(0));
}

void test_step_1_triples(void) {
    TEST_ASSERT_EQUAL_UINT32(360, computeBackoffSeconds(1));
}

void test_step_2_triples(void) {
    TEST_ASSERT_EQUAL_UINT32(1080, computeBackoffSeconds(2));
}

void test_step_3_triples(void) {
    TEST_ASSERT_EQUAL_UINT32(3240, computeBackoffSeconds(3));
}

void test_step_4_triples(void) {
    TEST_ASSERT_EQUAL_UINT32(9720, computeBackoffSeconds(4));
}

void test_step_5_triples(void) {
    TEST_ASSERT_EQUAL_UINT32(29160, computeBackoffSeconds(5));
}

void test_step_6_hits_24h_cap(void) {
    // 120 * 3^6 = 120 * 729 = 87480 > 86400 cap.
    TEST_ASSERT_EQUAL_UINT32(86400, computeBackoffSeconds(6));
}

void test_well_above_cap_stays_at_cap(void) {
    TEST_ASSERT_EQUAL_UINT32(86400, computeBackoffSeconds(100));
}

void test_negative_step_returns_base(void) {
    TEST_ASSERT_EQUAL_UINT32(120, computeBackoffSeconds(-1));
    TEST_ASSERT_EQUAL_UINT32(120, computeBackoffSeconds(-100));
}


int main(int argc, char **argv) {
    (void)argc; (void)argv;
    UNITY_BEGIN();
    RUN_TEST(test_step_0_is_2_minutes);
    RUN_TEST(test_step_1_triples);
    RUN_TEST(test_step_2_triples);
    RUN_TEST(test_step_3_triples);
    RUN_TEST(test_step_4_triples);
    RUN_TEST(test_step_5_triples);
    RUN_TEST(test_step_6_hits_24h_cap);
    RUN_TEST(test_well_above_cap_stays_at_cap);
    RUN_TEST(test_negative_step_returns_base);
    return UNITY_END();
}
