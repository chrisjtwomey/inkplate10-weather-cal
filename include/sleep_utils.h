#ifndef __SLEEP_H__
#define __SLEEP_H__
#include "time_utils.h"
/**
  Enter deep sleep.

  @param refreshTime the time of the day to wake in HH:MM:SS format (eg.
  09:00:00). error.
*/
void sleep(const char* refreshTime);

/**
  Enter deep sleep.

  @param targetWakeTime the target timestamp to wake up at.
*/
void sleep(time_t targetWakeTime);

void sleep(int targetWakeTime);

/**
  Enter deep sleep.
*/
void deepSleep();
#endif