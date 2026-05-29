// Stub implementations for functions declared in the project headers but
// whose real .cpp files drag in ESP32 / MQTT / WiFi libraries incompatible
// with the native host build.
//
// Compiled only in [env:native_mock] via build_src_filter.
// All definitions are guarded with #ifdef NATIVE so the IDE (which uses the
// ESP32 IntelliSense profile) does not report false-positive errors.

#ifdef NATIVE

#include <stdarg.h>
#include <string>

// log() and logf() conflict with the math.h functions of the same name on
// macOS (double log(double) / float logf(float)). Guard the stubs with the
// real log_utils.h include guard so they are only defined once, and use
// explicit C++ linkage to avoid the math.h clash.
#include "log_utils.h"   // pulls in the #define LOG_LEVEL guard

void log(uint16_t, const char*) {}
void logf(uint16_t, const char*, ...) {}

// Satisfy linker for time_utils.h declarations.
// Return type matches the header (String = std::string in the Arduino stub).
#include "time_utils.h"
String nowTzFmt() { return ""; }

// Satisfy linker for WiFiClass / SPIFFSClass globals referenced by stubs.
#include "WiFi.h"
WiFiClass WiFi;

#include "SPIFFS.h"
SPIFFSClass SPIFFS;

// Satisfy linker for globals declared extern in Arduino.h stub.
// (Serial and g_wakeup_cause are not used by native_mock tests but the
//  declarations in Arduino.h — pulled in via font headers — require them.)
#include "Arduino.h"
HardwareSerial Serial;
esp_sleep_wakeup_cause_t g_wakeup_cause = ESP_SLEEP_WAKEUP_UNDEFINED;

#endif // NATIVE

