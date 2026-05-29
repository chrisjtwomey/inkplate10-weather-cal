// driver/rtc_io.h stub for native host builds.
// sleep_utils.cpp calls esp_sleep_enable_ext0_wakeup() and
// esp_deep_sleep_start().  On the host these are no-ops so test execution
// continues normally after sleep() is called.
#ifndef __STUB_DRIVER_RTC_IO_H__
#define __STUB_DRIVER_RTC_IO_H__

#include <stdint.h>

typedef int gpio_num_t;
#define GPIO_NUM_39 39

inline int  esp_sleep_enable_ext0_wakeup(gpio_num_t, int) { return 0; }

// Must NOT call exit() or abort() — tests need to keep running after
// sleep() is invoked so assertions after the call-under-test can execute.
inline void esp_deep_sleep_start() {}

#endif // __STUB_DRIVER_RTC_IO_H__
