// Definitions for the config symbols declared in defaults.h.
//
// A consuming project supplies these in its own src/defaults.cpp. The library
// only declares them, so the integration test provides its own copy rather
// than compiling a defaults.cpp out of the library sources.

#ifdef NATIVE

#include <stdint.h>

char     serverURL[]  = "http://test.local:8080/image.png";
int      serverRetries = 3;
uint32_t serverDefaultRefreshSeconds = 3600;

char wifiSSID[] = "test-ssid";
char wifiPass[] = "test-pass";
int  wifiRetries = 10;

char ntpHost[]     = "pool.ntp.org";
char ntpTimezone[] = "Europe/Dublin";

bool mqttLoggerEnabled = false;
char mqttLoggerBroker[] = "localhost";
int  mqttLoggerPort = 1883;
char mqttLoggerClientID[] = "epaper-test-client";
char mqttLoggerTopic[] = "mqtt/epaper-test";
int  mqttLoggerRetries = 3;

#endif // NATIVE
