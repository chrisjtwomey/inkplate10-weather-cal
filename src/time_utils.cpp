#include "time_utils.h"
#include <Arduino.h>
#include <Inkplate.h>
#include <ezTime.h>

#include "error_utils.h"
#include "log_utils.h"

// The timezone store
Timezone myTz;

// The Inkplate board driver instance.
extern Inkplate board;

/**
 * Return a RFC3339 formatted string of the current time.
 * 
 * @return String the RFC3339 formatted string of the current time.
 */
String nowTzFmt() {
    return dateTime(myTz.now(), RFC3339);
}

/**
  Connect to an NTP server and synchronize the on-board real-time clock.

  @param host the hostname of the NTP server (eg. pool.ntp.org).
  @param timezoneName the name of the timezone in Olson format (eg.
  Europe/Dublin)
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_ENTP if updating the NTP client fails.
*/
esp_err_t configureTime(const char* ntpHost, const char* timezoneName) {
    log(LOG_INFO, "configuring network time and RTC...");

    setServer(ntpHost);

    if (!waitForSync()) {
        return ESP_ERR_ENTP;
    }
    myTz.setLocation(F(timezoneName));

    updateNTP();
    // Sync RTC with NTP time
    // time_t nowTime = now();
    time_t nowTime = myTz.now();
    board.rtcSetEpoch(nowTime);
    logf(LOG_DEBUG, "RTC synced to %s", dateTime(nowTime, RFC3339).c_str());

    return ESP_OK;
}

/**
  Get the next scheduled time to wake from deep sleep.

  @param refreshTime the time of the day to wake in HH::MM:SS format (eg.
  09:00:00). error.
  @returns the epoch time of when to wake.
  If the real-time clock is not configured, it will return the last
  configured RTC epoch time + FALLBACK_SLEEP_SECONDS.
*/
time_t getWakeTime(const char* refreshTime) {
    if (!board.rtcIsSet()) {
        log(LOG_WARNING, "cannot determine wake time: RTC not set");
        return board.rtcGetEpoch() + FALLBACK_SLEEP_SECONDS;
    }

    tmElements_t tm;
    int hr, min, sec;
    sscanf(refreshTime, "%d:%d:%d", &hr, &min, &sec);

    tm.Hour = hr;
    tm.Minute = min;
    tm.Second = sec;

    tm.Day = myTz.day();
    tm.Month = myTz.month();
    tm.Year = CalendarYrToTm(myTz.year());

    time_t targetTime = makeTime(tm);
    time_t nowTime = myTz.now();

    // Rollover to tomorrow
    if (nowTime > targetTime) {
        targetTime += SECS_PER_DAY;
    }

    return targetTime;
}
