// Minimal Arduino.h stub for native host builds.
// Provides the types and macros used by app.cpp / display_utils / sleep_utils
// without pulling in any ESP32 or Inkplate headers.
#ifndef __STUB_ARDUINO_H__
#define __STUB_ARDUINO_H__

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <string>
#include <cstdio>

// PROGMEM is a no-op on the host.
#define PROGMEM

// RTC_DATA_ATTR marks variables that survive deep-sleep on ESP32.
// On the host they are plain globals.
#define RTC_DATA_ATTR

// String class mirroring the Arduino String type.
// Inherits from std::string so existing .c_str() / comparison / assignment
// code works unchanged. Extra constructors cover the Arduino API surface
// used by the firmware (e.g. String(double, decimals)).
class String : public std::string {
public:
    String() : std::string() {}
    String(const char* s) : std::string(s ? s : "") {}
    String(const std::string& s) : std::string(s) {}
    String(double val, int decimals = 2) {
        char buf[32];
        snprintf(buf, sizeof(buf), "%.*f", decimals, val);
        assign(buf);
    }
    String(int val)           : std::string(std::to_string(val)) {}
    String(unsigned int val)  : std::string(std::to_string(val)) {}
    String(long val)          : std::string(std::to_string(val)) {}
    String(unsigned long val) : std::string(std::to_string(val)) {}
    bool isEmpty() const { return empty(); }
};

// Colour constants used by display_utils.cpp.
#define BLACK  0x00
#define WHITE  0xFF

// GFX font types (normally from Adafruit_GFX). Defined here so font headers
// that include Arduino.h compile cleanly without the Inkplate library.
typedef struct {
    uint16_t bitmapOffset;
    uint8_t  width;
    uint8_t  height;
    uint8_t  xAdvance;
    int8_t   xOffset;
    int8_t   yOffset;
} GFXglyph;

typedef struct {
    uint8_t*  bitmap;
    GFXglyph* glyph;
    uint8_t   first;
    uint8_t   last;
    uint8_t   yAdvance;
} GFXfont;

// Minimal HardwareSerial stub — enough for Serial.begin() in app.cpp.
struct HardwareSerial {
    void begin(int) {}
};
extern HardwareSerial Serial;

// esp_sleep types and functions (normally pulled in via Arduino.h on ESP32).
typedef enum {
    ESP_SLEEP_WAKEUP_UNDEFINED = 0,
    ESP_SLEEP_WAKEUP_ALL       = 1,
    ESP_SLEEP_WAKEUP_EXT0      = 2,
    ESP_SLEEP_WAKEUP_EXT1      = 3,
    ESP_SLEEP_WAKEUP_TIMER     = 4,
    ESP_SLEEP_WAKEUP_TOUCHPAD  = 5,
    ESP_SLEEP_WAKEUP_ULP       = 6,
    ESP_SLEEP_WAKEUP_GPIO      = 7,
    ESP_SLEEP_WAKEUP_UART      = 8,
} esp_sleep_wakeup_cause_t;

// Configurable in tests; set g_wakeup_cause before calling run_app() to
// simulate different hardware wakeup sources.
extern esp_sleep_wakeup_cause_t g_wakeup_cause;
inline esp_sleep_wakeup_cause_t esp_sleep_get_wakeup_cause() {
    return g_wakeup_cause;
}

#endif // __STUB_ARDUINO_H__

