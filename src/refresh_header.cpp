#include "refresh_header.h"

bool parseRefreshTime(const char* headerVal, uint32_t* out) {
    if (!headerVal || !out || *headerVal == '\0') return false;

    uint64_t acc = 0;
    for (const char* p = headerVal; *p; ++p) {
        if (*p < '0' || *p > '9') return false;
        acc = acc * 10 + (uint64_t)(*p - '0');
        if (acc > UINT32_MAX) return false;
    }
    *out = (uint32_t)acc;
    return true;
}
