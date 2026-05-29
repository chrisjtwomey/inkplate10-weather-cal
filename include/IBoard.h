#ifndef __IBOARD_H__
#define __IBOARD_H__

#include <Arduino.h>
#include <time.h>

// Opaque handle for a font resource. Implementations backed by Adafruit GFX
// should treat this as a const GFXfont* and cast accordingly. Using an opaque
// pointer keeps IBoard free of any library-specific header dependencies.
typedef const void* FontHandle;

/**
 * Abstract board interface.
 *
 * Decouples application logic from the Inkplate hardware driver. To support
 * a different device, subclass IBoard and implement every pure-virtual method.
 * Then replace the InkplateBoard instance in main.cpp with your own.
 */
class IBoard {
public:
    virtual ~IBoard() {}

    // -------------------------------------------------------------------------
    // Lifecycle
    // -------------------------------------------------------------------------

    /** Initialise the hardware. Called once at startup before any other method. */
    virtual void begin() = 0;

    /** Set display rotation (0-3, matching Adafruit GFX convention). */
    virtual void setRotation(uint8_t r) = 0;

    /** Physical display width in pixels (before any rotation is applied). */
    virtual int16_t getWidth() const = 0;

    /** Physical display height in pixels (before any rotation is applied). */
    virtual int16_t getHeight() const = 0;

    // -------------------------------------------------------------------------
    // Display output
    // -------------------------------------------------------------------------

    /** Clear the in-memory frame buffer to white. */
    virtual void clearDisplay() = 0;

    /** Push the in-memory frame buffer to the physical display. */
    virtual void display() = 0;

    // -------------------------------------------------------------------------
    // Image drawing (into the frame buffer)
    // -------------------------------------------------------------------------

    /**
     * Decode a PNG from a raw byte buffer and draw it at (x, y).
     *
     * @param buf     pointer to the PNG bytes.
     * @param len     byte count.
     * @param x       top-left x coordinate.
     * @param y       top-left y coordinate.
     * @param dither  enable dithering.
     * @param invert  invert colours.
     * @returns true on success.
     */
    virtual bool drawPngFromBuffer(uint8_t* buf, int32_t len,
                                   int x, int y,
                                   bool dither, bool invert) = 0;

    /**
     * Decode a PNG from a file on SD card and draw it at (x, y).
     *
     * @param path    absolute path on the SD card.
     * @param x       top-left x coordinate.
     * @param y       top-left y coordinate.
     * @param dither  enable dithering.
     * @param invert  invert colours.
     * @returns true on success.
     */
    virtual bool drawPngFromSd(const char* path,
                               int x, int y,
                               bool dither, bool invert) = 0;

    /**
     * Draw a raw 1-bit bitmap at (x, y).
     *
     * @param buf  byte array of bitmap data.
     * @param x    top-left x coordinate.
     * @param y    top-left y coordinate.
     * @param w    bitmap width in pixels.
     * @param h    bitmap height in pixels.
     * @param fg   foreground colour.
     * @param bg   background colour.
     * @returns true on success.
     */
    virtual bool drawBitmap(uint8_t* buf,
                            int x, int y, int w, int h,
                            uint16_t fg, uint16_t bg) = 0;

    // -------------------------------------------------------------------------
    // Text / GFX primitives (Adafruit GFX compatible)
    // -------------------------------------------------------------------------

    virtual void setFont(FontHandle font) = 0;
    virtual void setTextSize(uint8_t s) = 0;
    virtual void setTextColor(uint16_t c) = 0;
    virtual void setTextWrap(bool wrap) = 0;
    virtual void getTextBounds(const char* str,
                               int16_t x, int16_t y,
                               int16_t* x1, int16_t* y1,
                               uint16_t* w, uint16_t* h) = 0;
    virtual void setCursor(int16_t x, int16_t y) = 0;
    virtual void print(const char* str) = 0;
    virtual void print(const String& str) = 0;
    virtual void fillRect(int16_t x, int16_t y,
                          int16_t w, int16_t h,
                          uint16_t color) = 0;

    // -------------------------------------------------------------------------
    // Battery
    // -------------------------------------------------------------------------

    /** Read and return the current battery voltage. */
    virtual double readBattery() = 0;

    // -------------------------------------------------------------------------
    // RTC
    // -------------------------------------------------------------------------

    /** Refresh the in-memory RTC state from hardware registers. */
    virtual void rtcGetData() = 0;

    /** Return the current epoch time as held by the RTC. */
    virtual time_t rtcGetEpoch() = 0;

    /** Clear any pending RTC alarm flag. */
    virtual void rtcClearAlarmFlag() = 0;

    /**
     * Set an RTC alarm to fire at the given epoch time.
     * The implementation is responsible for any hardware-specific alarm-match
     * mode details (e.g. day/hour/minute/second matching).
     *
     * @param epoch  the Unix timestamp at which the alarm should fire.
     */
    virtual void rtcSetAlarmEpoch(time_t epoch) = 0;

    // -------------------------------------------------------------------------
    // SD card (only required when USE_SDCARD is defined)
    // -------------------------------------------------------------------------

#if defined(USE_SDCARD)
    /** Initialise the SD card. Returns true on success. */
    virtual bool sdCardInit() = 0;

    /** Put the SD card into low-power sleep mode. */
    virtual void sdCardSleep() = 0;

    // getSdFat() is intentionally absent from this interface: SdFat is a
    // type bundled inside InkplateLibrary and cannot be used as a return type
    // here without creating a library dependency in IBoard. Call sites that
    // need direct SdFat access should include InkplateBoard.h and downcast:
    //   static_cast<InkplateBoard&>(board).getSdFat()
#endif
};

#endif // __IBOARD_H__
