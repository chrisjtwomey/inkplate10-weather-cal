// WiFi.h stub for native host builds.
// sleep_utils.cpp calls WiFi.disconnect() and WiFi.mode() before deep sleep.
// Both are no-ops on the host.
#ifndef __STUB_WIFI_H__
#define __STUB_WIFI_H__

#define WIFI_OFF 0

class WiFiClass {
public:
    void disconnect() {}
    void mode(int)    {}
};

extern WiFiClass WiFi;

#endif // __STUB_WIFI_H__
