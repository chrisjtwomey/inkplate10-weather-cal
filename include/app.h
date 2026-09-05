#ifndef __APP_H__
#define __APP_H__

#include <stdint.h>

#include "settings.h"

/**
 * Main application logic (body of Arduino setup()).
 *
 * epdBegin() must have been called first, so the library has a board. Kept
 * out of main.cpp so integration tests can invoke run_app() directly with a
 * MockBoard and controllable free-function stubs.
 */
void run_app();

/**
 * The settings this image was built with, from src/defaults.cpp.
 *
 * epd declares no settings symbols of its own, so where a project hard-codes
 * its own is the project's business. This is ours.
 */
ClientConfig compiledDefaults();

#ifdef NATIVE
// In native (test) builds, expose the RTC-backed persistent state so tests
// can inspect it and reset it between runs via reset_app_state().
extern int      bootCount;
extern uint32_t nextRefreshSeconds;
extern int      serverBackoffStep;
extern char     nextServerURL[256];

// Zero-initialise all persistent application state (call in test setUp()).
void reset_app_state();
#endif

#endif // __APP_H__
