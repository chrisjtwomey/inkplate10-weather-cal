#ifndef __INKPLATEBOARD_H__
#define __INKPLATEBOARD_H__

#include <Inkplate.h>
#include "IBoard.h"

/**
 * Inkplate implementation of IBoard.
 *
 * Wraps an Inkplate driver instance and delegates every IBoard method to the
 * corresponding Inkplate API call. This is the only file that depends on the
 * Inkplate library — all other client code depends only on IBoard.
 */
class InkplateBoard : public IBoard {
public:
    InkplateBoard();

    // Lifecycle
    void begin() override;
    void setRotation(uint8_t r) override;
    int16_t getWidth() const override;
    int16_t getHeight() const override;

    // Display output
    void clearDisplay() override;
    void display() override;

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
    void setFont(FontHandle font) override;
    void setTextSize(uint8_t s) override;
    void setTextColor(uint16_t c) override;
    void setTextWrap(bool wrap) override;
    void getTextBounds(const char* str,
                       int16_t x, int16_t y,
                       int16_t* x1, int16_t* y1,
                       uint16_t* w, uint16_t* h) override;
    void setCursor(int16_t x, int16_t y) override;
    void print(const char* str) override;
    void print(const String& str) override;
    void fillRect(int16_t x, int16_t y,
                  int16_t w, int16_t h,
                  uint16_t color) override;

    // Battery
    double readBattery() override;

    // RTC
    void rtcGetData() override;
    time_t rtcGetEpoch() override;
    void rtcClearAlarmFlag() override;
    void rtcSetAlarmEpoch(time_t epoch) override;

#if defined(USE_SDCARD)
    // SD card
    bool sdCardInit() override;
    void sdCardSleep() override;
    // getSdFat() is not part of IBoard: SdFat is InkplateLibrary-specific.
    // Call sites that need it must include this header and downcast to InkplateBoard&.
    SdFat& getSdFat();
#endif

private:
    Inkplate _inkplate;
};

#endif // __INKPLATEBOARD_H__
