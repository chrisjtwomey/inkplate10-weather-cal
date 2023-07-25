#ifndef __TIME_UTILS_H__
#define __TIME_UTILS_H__
#include <Arduino.h> 
#include "error_utils.h"

#define CalendarYrToTm(Y) ((Y)-1970)
#define SECONDS_IN_DAY 86400
#define SECONDS_IN_YEAR SECONDS_IN_DAY * 365

// The number of seconds to sleep if RTC not configured correctly.
#define FALLBACK_SLEEP_SECONDS 120

/**
 * Return a RFC3339 formatted string of the current time.
 * 
 * @return String the RFC3339 formatted string of the current time.
 */
String nowTzFmt();

/**
  Connect to an NTP server and synchronize the on-board real-time clock.

  @param ntpHost the hostname of the NTP server (eg. pool.ntp.org).
  @param timezoneName the name of the timezone in Olson format (eg.
  Europe/Dublin)
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_ENTP if updating the NTP client fails.
*/
esp_err_t configureTime(const char* ntpHost, const char* timezoneName);

/**
  Get the next scheduled time to wake from deep sleep.

  @param refreshTime the time of the day to wake in HH::MM:SS format (eg.
  09:00:00). error.
  @returns the epoch time of when to wake.
  If the real-time clock is not configured, it will return the last configured
  RTC epoch time + FALLBACK_SLEEP_SECONDS.
*/
time_t getWakeTime(const char* refreshTime);
#endif