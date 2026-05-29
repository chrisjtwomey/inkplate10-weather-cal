#ifndef __APP_H__
#define __APP_H__

#include <stdint.h>

/**
 * Main application logic (body of Arduino setup()).
 *
 * The IBoard& board global must be defined by the calling translation unit.
 * Extracted here so integration tests can invoke run_app() directly with a
 * MockBoard and controllable free-function stubs.
 */
void run_app();

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
