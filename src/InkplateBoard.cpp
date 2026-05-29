#include "InkplateBoard.h"

InkplateBoard::InkplateBoard() : _inkplate(INKPLATE_3BIT) {}

// -----------------------------------------------------------------------------
// Lifecycle
// -----------------------------------------------------------------------------

void InkplateBoard::begin() {
    _inkplate.begin();
}

void InkplateBoard::setRotation(uint8_t r) {
    _inkplate.setRotation(r);
}

int16_t InkplateBoard::getWidth() const {
    return E_INK_WIDTH;
}

int16_t InkplateBoard::getHeight() const {
    return E_INK_HEIGHT;
}

// -----------------------------------------------------------------------------
// Display output
// -----------------------------------------------------------------------------

void InkplateBoard::clearDisplay() {
    _inkplate.clearDisplay();
}

void InkplateBoard::display() {
    _inkplate.display();
}

// -----------------------------------------------------------------------------
// Image drawing
// -----------------------------------------------------------------------------

bool InkplateBoard::drawPngFromBuffer(uint8_t* buf, int32_t len,
                                      int x, int y,
                                      bool dither, bool invert) {
    return _inkplate.image.drawPngFromBuffer(buf, len, x, y, dither, invert);
}

bool InkplateBoard::drawPngFromSd(const char* path,
                                  int x, int y,
                                  bool dither, bool invert) {
    return _inkplate.image.drawPngFromSd(path, x, y, dither, invert);
}

bool InkplateBoard::drawBitmap(uint8_t* buf,
                               int x, int y, int w, int h,
                               uint16_t fg, uint16_t bg) {
    return _inkplate.image.draw(buf, x, y, w, h, fg, bg);
}

// -----------------------------------------------------------------------------
// Text / GFX
// -----------------------------------------------------------------------------

void InkplateBoard::setFont(FontHandle font) {
    _inkplate.setFont(reinterpret_cast<const GFXfont*>(font));
}

void InkplateBoard::setTextSize(uint8_t s) {
    _inkplate.setTextSize(s);
}

void InkplateBoard::setTextColor(uint16_t c) {
    _inkplate.setTextColor(c);
}

void InkplateBoard::setTextWrap(bool wrap) {
    _inkplate.setTextWrap(wrap);
}

void InkplateBoard::getTextBounds(const char* str,
                                  int16_t x, int16_t y,
                                  int16_t* x1, int16_t* y1,
                                  uint16_t* w, uint16_t* h) {
    _inkplate.getTextBounds(str, x, y, x1, y1, w, h);
}

void InkplateBoard::setCursor(int16_t x, int16_t y) {
    _inkplate.setCursor(x, y);
}

void InkplateBoard::print(const char* str) {
    _inkplate.print(str);
}

void InkplateBoard::print(const String& str) {
    _inkplate.print(str);
}

void InkplateBoard::fillRect(int16_t x, int16_t y,
                             int16_t w, int16_t h,
                             uint16_t color) {
    _inkplate.fillRect(x, y, w, h, color);
}

// -----------------------------------------------------------------------------
// Battery
// -----------------------------------------------------------------------------

double InkplateBoard::readBattery() {
    return _inkplate.readBattery();
}

// -----------------------------------------------------------------------------
// RTC
// -----------------------------------------------------------------------------

void InkplateBoard::rtcGetData() {
    _inkplate.rtc.getRtcData();
}

time_t InkplateBoard::rtcGetEpoch() {
    return _inkplate.rtc.getEpoch();
}

void InkplateBoard::rtcClearAlarmFlag() {
    _inkplate.rtc.clearAlarmFlag();
}

void InkplateBoard::rtcSetAlarmEpoch(time_t epoch) {
    // RTC_ALARM_MATCH_DHHMMSS is the Inkplate-specific alarm match mode;
    // hidden here so callers depend only on the IBoard interface.
    _inkplate.rtc.setAlarmEpoch(epoch, RTC_ALARM_MATCH_DHHMMSS);
}

// -----------------------------------------------------------------------------
// SD card
// -----------------------------------------------------------------------------

#if defined(USE_SDCARD)
bool InkplateBoard::sdCardInit() {
    return _inkplate.sdCardInit();
}

void InkplateBoard::sdCardSleep() {
    _inkplate.sdCardSleep();
}

SdFat& InkplateBoard::getSdFat() {
    return _inkplate.getSdFat();
}
#endif
