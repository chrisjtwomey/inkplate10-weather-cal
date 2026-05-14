#ifndef __SLEEP_H__
#define __SLEEP_H__
#include "time_utils.h"
#include <stdint.h>

/**
  Enter deep sleep for `seconds` from now. Wakes via the external RTC alarm.
  The server is the single source of truth for *when* — the client just
  counts down.
*/
void sleep_for(uint32_t seconds);

/**
  Enter deep sleep until the given RTC epoch.
*/
void sleep(time_t targetWakeTime);

/**
  Enter deep sleep with no scheduled wake (only external triggers).
*/
void deepSleep();
#endif