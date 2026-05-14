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
    board.rtc.setEpoch(nowTime);
    logf(LOG_DEBUG, "RTC synced to %s", dateTime(nowTime, RFC3339).c_str());

    return ESP_OK;
}

