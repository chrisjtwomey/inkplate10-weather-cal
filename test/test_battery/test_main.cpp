// Native tests for the battery voltage-to-capacity lookup table.
//
// getBatteryCapacity() is a pure table-scan function — no hardware, no
// Arduino.h. Tests verify the known boundaries and a spread of typical
// in-use voltages.

#include <unity.h>
#include "battery.h"


void test_full_charge_voltage(void) {
    // 4.25 V is the first entry and should map to 100%.
    TEST_ASSERT_EQUAL_INT(100, getBatteryCapacity(4.25));
}

void test_above_full_charge_voltage(void) {
    // Anything above the highest table entry should still return 100%.
    TEST_ASSERT_EQUAL_INT(100, getBatteryCapacity(4.30));
    TEST_ASSERT_EQUAL_INT(100, getBatteryCapacity(5.00));
}

void test_dead_voltage(void) {
    // 3.10 V is the last entry and should map to 0%.
    TEST_ASSERT_EQUAL_INT(0, getBatteryCapacity(3.10));
}

void test_below_dead_voltage(void) {
    // Below the lowest entry the loop exhausts and returns 0.
    TEST_ASSERT_EQUAL_INT(0, getBatteryCapacity(2.50));
    TEST_ASSERT_EQUAL_INT(0, getBatteryCapacity(0.00));
}

void test_mid_range_voltages(void) {
    // Spot-check a handful of values from the table.
    TEST_ASSERT_EQUAL_INT(50, getBatteryCapacity(3.79));
    TEST_ASSERT_EQUAL_INT(30, getBatteryCapacity(3.64));
    TEST_ASSERT_EQUAL_INT(10, getBatteryCapacity(3.40));
}

void test_low_battery_threshold(void) {
    // The firmware treats <=10% as "battery low" and <=1% as "empty".
    TEST_ASSERT_EQUAL_INT(10, getBatteryCapacity(3.40));
    TEST_ASSERT_EQUAL_INT(1,  getBatteryCapacity(3.16));
}

void test_returns_highest_matching_entry(void) {
    // Table is scanned top-to-bottom; first entry where voltage >= threshold
    // wins. 4.08 V appears for four consecutive percentages (89/88/87/86);
    // the highest (89) must be returned.
    TEST_ASSERT_EQUAL_INT(89, getBatteryCapacity(4.08));
}

void test_voltage_just_below_entry_falls_through(void) {
    // 4.07 V falls through the 4.08 entries and hits the first 4.07 entry.
    TEST_ASSERT_EQUAL_INT(85, getBatteryCapacity(4.07));
}


int main(int argc, char **argv) {
    (void)argc; (void)argv;
    UNITY_BEGIN();
    RUN_TEST(test_full_charge_voltage);
    RUN_TEST(test_above_full_charge_voltage);
    RUN_TEST(test_dead_voltage);
    RUN_TEST(test_below_dead_voltage);
    RUN_TEST(test_mid_range_voltages);
    RUN_TEST(test_low_battery_threshold);
    RUN_TEST(test_returns_highest_matching_entry);
    RUN_TEST(test_voltage_just_below_entry_falls_through);
    return UNITY_END();
}
