# Integrating a custom board

The firmware abstracts all hardware-specific behaviour behind the `IBoard`
interface (declared in `include/IBoard.h`).  The only file that depends on the
Inkplate library is `InkplateBoard` — everything else works against `IBoard`.
To support a different e-paper device you subclass `IBoard`, implement every
pure-virtual method, and swap the instance in `src/main.cpp`.

## 1. Understand the interface

`IBoard` is divided into five sections.

### Lifecycle

| Method | Purpose |
|---|---|
| `deviceName() const` | Human-readable device label used in boot log lines. |
| `begin()` | One-time hardware initialisation, called at startup before any other method. |
| `setRotation(r)` | Set display rotation 0–3 (Adafruit GFX convention: 0 = portrait, 1 = landscape, …). |
| `getWidth() const` | Physical panel width in pixels **before** rotation is applied. |
| `getHeight() const` | Physical panel height in pixels **before** rotation is applied. |

### Display output

| Method | Purpose |
|---|---|
| `clearDisplay()` | Erase the in-memory frame buffer to white. |
| `display()` | Flush the in-memory frame buffer to the physical panel. |

### Image drawing (into the frame buffer)

| Method | Purpose |
|---|---|
| `drawPngFromBuffer(buf, len, x, y, dither, invert)` | Decode a PNG from a byte buffer and render it at `(x, y)`. Returns `true` on success. |
| `drawPngFromSd(path, x, y, dither, invert)` | Decode a PNG from an SD-card file and render it at `(x, y)`. Returns `true` on success. Only called when `USE_SDCARD` is defined. |
| `drawBitmap(buf, x, y, w, h, fg, bg)` | Draw a raw 1-bit bitmap at `(x, y)`. Used for battery status icons. Returns `true` on success. |

### Text / GFX primitives

These mirror the [Adafruit GFX](https://github.com/adafruit/Adafruit-GFX-Library) API so that drivers backed by a compatible library can delegate calls directly.

| Method | Notes |
|---|---|
| `setFont(font)` | `FontHandle` is `const void*`; cast to `const GFXfont*` for Adafruit GFX. |
| `setTextSize(s)` | Scale factor (1 = native). |
| `setTextColor(c)` | 16-bit colour value. |
| `setTextWrap(wrap)` | Enable/disable line wrapping. |
| `getTextBounds(str, x, y, x1, y1, w, h)` | Write bounding box of `str` into the out-params. |
| `setCursor(x, y)` | Move the text cursor. |
| `print(str)` | Draw a null-terminated string at the current cursor. |
| `print(str)` | Overload accepting `const String&`. |
| `fillRect(x, y, w, h, color)` | Fill a solid rectangle. Used for the banner background in `displayMessage`. |

### Battery

| Method | Notes |
|---|---|
| `readBattery()` | Return the current battery voltage in volts as a `double`. |

### RTC

The firmware relies entirely on the hardware RTC for deep-sleep scheduling.
No NTP math or timezone awareness is required on the client — the server
sends an `X-Next-Refresh-Seconds` header and the client simply adds that
offset to the current epoch when setting the alarm.

| Method | Notes |
|---|---|
| `rtcGetData()` | Read hardware RTC registers into memory. Called once at startup. |
| `rtcGetEpoch()` | Return the current Unix timestamp held in the RTC. |
| `rtcClearAlarmFlag()` | Clear any pending alarm interrupt flag (called on `ESP_SLEEP_WAKEUP_EXT0`). |
| `rtcSetAlarmEpoch(epoch)` | Program the RTC alarm to fire at `epoch`. All alarm-match mode details are encapsulated inside the implementation. |

### SD card (`USE_SDCARD` only)

These methods are compiled only when the `USE_SDCARD` build flag is set.

| Method | Notes |
|---|---|
| `sdCardInit()` | Initialise the SD card. Returns `true` on success. |
| `sdCardSleep()` | Put the SD card into low-power sleep before deep sleep. |

> **Note on `getSdFat()`:** `InkplateBoard` exposes a `getSdFat()` method to
> give `app.cpp` direct access to the `SdFat` object for YAML config loading.
> This method intentionally does **not** appear on `IBoard` because `SdFat`
> is a type bundled inside InkplateLibrary.  Call sites that need it use a
> downcast: `static_cast<InkplateBoard&>(board).getSdFat()`.  If your driver
> uses a different SD library you can expose a comparable accessor the same way.

---

## 2. Create your driver

Add your header and implementation files anywhere the build system can find
them — `include/` and `src/` are the simplest choices.

**`include/MyBoard.h`**

```cpp
#pragma once
#include "IBoard.h"

class MyBoard : public IBoard {
public:
    MyBoard();

    // Lifecycle
    const char* deviceName() const override;
    void        begin()              override;
    void        setRotation(uint8_t r) override;
    int16_t     getWidth()  const    override;
    int16_t     getHeight() const    override;

    // Display output
    void clearDisplay() override;
    void display()      override;

    // Image drawing
    bool drawPngFromBuffer(uint8_t* buf, int32_t len,
                           int x, int y,
                           bool dither, bool invert) override;
    bool drawPngFromSd(const char* path,
                       int x, int y,
                       bool dither, bool invert) override;
    bool drawBitmap(uint8_t* buf,
                    int x, int y, int w, int h,
                    uint16_t fg, uint16_t bg) override;

    // Text / GFX
    void setFont(FontHandle font)                   override;
    void setTextSize(uint8_t s)                     override;
    void setTextColor(uint16_t c)                   override;
    void setTextWrap(bool wrap)                     override;
    void getTextBounds(const char* str,
                       int16_t x,  int16_t y,
                       int16_t* x1, int16_t* y1,
                       uint16_t* w, uint16_t* h)   override;
    void setCursor(int16_t x, int16_t y)            override;
    void print(const char* str)                     override;
    void print(const String& str)                   override;
    void fillRect(int16_t x, int16_t y,
                  int16_t w, int16_t h,
                  uint16_t color)                   override;

    // Battery
    double readBattery() override;

    // RTC
    void   rtcGetData()                    override;
    time_t rtcGetEpoch()                   override;
    void   rtcClearAlarmFlag()             override;
    void   rtcSetAlarmEpoch(time_t epoch)  override;

#if defined(USE_SDCARD)
    bool sdCardInit()  override;
    void sdCardSleep() override;
#endif

private:
    // Your hardware driver instance goes here, e.g.:
    // MyEpaperDriver _driver;
};
```

Implement each method in `src/MyBoard.cpp`, wrapping your hardware driver.
Refer to `src/InkplateBoard.cpp` as a concrete example of what each method
should do.

---

## 3. Swap the instance in `src/main.cpp`

`main.cpp` is the only file you need to change to switch hardware:

```cpp
// Before (Inkplate10)
#include "InkplateBoard.h"
static InkplateBoard inkplateBoard;
IBoard& board = inkplateBoard;

// After (your device)
#include "MyBoard.h"
static MyBoard myBoard;
IBoard& board = myBoard;
```

All other source files (`app.cpp`, `display_utils.cpp`, `sleep_utils.cpp`, …)
call `board` through the `IBoard` reference and require no changes.

---

## 4. Update `platformio.ini` if needed

If your driver depends on a different library, add it under `lib_deps` in the
relevant environment inside `platformio.ini`.  The `[esp32_common]` section
is shared by the `debug`, `release`, and `release_sdcard` environments:

```ini
[esp32_common]
lib_deps =
    ; keep existing entries…
    your-vendor/YourLibrary@^1.0.0
```

If your device is not an ESP32, create a new `[env:yourboard]` block instead
of extending `[esp32_common]`, setting `platform`, `board`, and `framework`
appropriately.

---

## 5. Testing without hardware

`MockBoard` (in `include/MockBoard.h`) is a fully working `IBoard` subclass
used by the host-side test environments (`native_mock`, `native_integration`).
Every method is a configurable no-op with call-tracking fields.  If you add
new methods to `IBoard` in the future, add matching no-ops to `MockBoard` too
so the test environments continue to compile.

To run the existing host-side tests against your own `IBoard` changes:

```sh
pio test -e native          # pure helper tests (backoff, battery, refresh_header)
pio test -e native_mock     # display_utils and sleep_utils with MockBoard
pio test -e native_integration  # full run_app() control-flow tests
```
