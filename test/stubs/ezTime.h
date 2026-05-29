// ezTime.h stub for native host builds.
// sleep_utils.cpp uses dateTime() for a log message and setTime().
// display_utils.cpp calls nowTzFmt() (declared in time_utils.h; stubbed in
// stubs.cpp).
#ifndef __STUB_EZTIME_H__
#define __STUB_EZTIME_H__

#include <string>
#include <time.h>

#define RFC3339 0

inline std::string dateTime(time_t, int = 0) { return ""; }
inline void        setTime(time_t)            {}

#endif // __STUB_EZTIME_H__
