// What panel.cpp calls but this test does not exercise.
//
// The panel's own drawing goes to MockBoard, which records it. Everything
// below is the surrounding kit: logging, the clock, and the cached page a
// banner is drawn over.
#include <Arduino.h>

#include "image.h"
#include "log_utils.h"
#include "time_utils.h"

void log(uint16_t, const char*) {}
void logf(uint16_t, const char*, ...) {}

String nowTzFmt() { return "Mon 1 Jan 00:00"; }

bool startImageCache() { return true; }
bool saveImageCache(const uint8_t*, int32_t) { return true; }
bool loadImageCache() { return true; }
