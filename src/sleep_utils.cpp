#include "sleep_utils.h"
#include <Inkplate.h>
#include <driver/rtc_io.h>
#include <rom/rtc.h>
#include <ezTime.h>

#include "log_utils.h"

// The Inkplate board driver instance.
extern Inkplate board;

/**
  Enter deep sleep with RTC alarm.

  @param refreshTime the time of the day to wake in HH:MM:SS format (eg.
  09:00:00). error.
*/
void sleep(const char* refreshTime) { 
  time_t targetWakeTime = getWakeTime(refreshTime);
  sleep(targetWakeTime);
}

void sleep(time_t targetWakeTime) {
    logf(LOG_DEBUG, "setting deep sleep RTC wakeup on pin %d", GPIO_NUM_39);

    board.rtcSetAlarmEpoch(targetWakeTime, RTC_ALARM_MATCH_DHHMMSS);
    esp_sleep_enable_ext0_wakeup(GPIO_NUM_39, 0);

    logf(LOG_DEBUG, "waking at %s", dateTime(targetWakeTime, RFC3339).c_str());

    deepSleep();
}

/**
  Enter deep sleep.
*/
void deepSleep() {
    log(LOG_NOTICE, "deep sleeping now");
    WiFi.disconnect();
    WiFi.mode(WIFI_OFF);

#if defined(USE_SDCARD)
    board.sdCardSleep();
#endif

    esp_deep_sleep_start();
}