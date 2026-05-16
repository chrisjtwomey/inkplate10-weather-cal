#ifndef __BACKOFF_H__
#define __BACKOFF_H__

#include <stdint.h>

/**
 * Returns seconds to sleep at the given back-off step.
 *
 * Starts at 120s (2 min) at step 0, triples each step, capped at
 * 86400s (24 hours). Negative steps are treated as step 0.
 *
 * Sequence: 120, 360, 1080, 3240, 9720, 29160, 86400, 86400, ...
 *
 * Pure: no hardware, no globals. Tested in test/test_backoff/.
 */
uint32_t computeBackoffSeconds(int step);

#endif
