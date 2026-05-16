#include "backoff.h"

uint32_t computeBackoffSeconds(int step) {
    const uint32_t CAP = 86400u;   // 24 hours
    const uint32_t BASE = 120u;    // 2 minutes
    const uint32_t MULTIPLIER = 3u;

    if (step <= 0) return BASE;

    uint32_t val = BASE;
    for (int i = 0; i < step; i++) {
        if (val >= CAP / MULTIPLIER) return CAP;  // next multiply would hit/exceed cap
        val *= MULTIPLIER;
    }
    return val < CAP ? val : CAP;
}
