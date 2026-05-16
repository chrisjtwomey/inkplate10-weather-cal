#ifndef __TIME_UTILS_H__
#define __TIME_UTILS_H__
#include <Arduino.h>
#include "error_utils.h"

#define SECONDS_IN_DAY 86400
#define SECONDS_IN_YEAR SECONDS_IN_DAY * 365

/**
 * Return a RFC3339 formatted string of the current time.
 *
 * @return String the RFC3339 formatted string of the current time.
 */
String nowTzFmt();

/**
  Connect to an NTP server and synchronize the on-board real-time clock.

  Used for log timestamps and error overlays only; wake scheduling is
  driven entirely by the server's X-Next-Refresh-Seconds header.

  @param ntpHost the hostname of the NTP server (eg. pool.ntp.org).
  @param timezoneName the name of the timezone in Olson format (eg.
  Europe/Dublin)
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_ENTP if updating the NTP client fails.
*/
esp_err_t configureTime(const char* ntpHost, const char* timezoneName);
#endif