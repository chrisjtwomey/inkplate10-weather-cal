#ifndef __REFRESH_HEADER_H__
#define __REFRESH_HEADER_H__

#include <stdint.h>
#include <stdbool.h>

/**
 * Parse the X-Next-Refresh-Seconds response header value into `*out`.
 *
 * The server sends a non-negative integer seconds-until-next-refresh. Returns
 * true and writes the parsed value to `*out` on success; returns false and
 * leaves `*out` unchanged on parse failure (null pointer, empty string, any
 * non-digit character, or value > UINT32_MAX).
 */
bool parseRefreshTime(const char* headerVal, uint32_t* out);

#endif
