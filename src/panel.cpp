#include "panel.h"

#include "epd.h"
#include "display_utils.h"
#include "font/Merienda_Regular12pt7b.h"
#include "font/Merienda_Regular16pt7b.h"
#include "icon/icons_32x32.h"
#include "log_utils.h"
#include "time_utils.h"
#include "version.h"

// Where the running version sits: top-left, clear of the battery indicator
// in the opposite corner.
#define VERSION_TEXT_X 12
#define VERSION_TEXT_Y 32

// The version, small, in the corner of every page. It is the only proof from
// across the room that an update landed: the number changes and nobody went
// near the board.
void drawClientVersion() {
    epdBoard().setFont(&Merienda_Regular12pt7b);
    epdBoard().setTextSize(1);
    epdBoard().setTextColor(BLACK);
    epdBoard().setCursor(VERSION_TEXT_X, VERSION_TEXT_Y);
    epdBoard().print(CLIENT_VERSION);
}

void displayMessage(const char* msg, int batteryRemainingPercent) {
    // Restore the cached image so the banner overlays it rather than
    // replacing the whole screen with white. drawPngFromBuffer writes every
    // pixel of the full-size PNG, so no clearDisplay() is needed before
    // or after — it either fills the buffer with the image, or the buffer
    // stays as-is (white from epdBoard().begin()) if no cache exists yet.
    loadImageCache();

    int cX = epdBoard().getHeight() / 2;
    int cY = 16;  // 16pt font
    int16_t x, y;
    uint16_t w, h;
    epdBoard().setFont(&Merienda_Regular16pt7b);
    epdBoard().setTextSize(1);
    epdBoard().setTextColor(BLACK);
    epdBoard().setTextWrap(true);
    epdBoard().getTextBounds(msg, 0, 0, &x, &y, &w, &h);
    epdBoard().fillRect(0, 0, epdBoard().getHeight(), h * 2.5, 0x8080);
    epdBoard().setCursor(cX - w / 2, cY + h * 1.5);
    epdBoard().setTextColor(0xFFFF);
    epdBoard().print(msg);

    String nowFmt = nowTzFmt();
    epdBoard().setFont(&Merienda_Regular12pt7b);
    epdBoard().setCursor(12, 24);
    epdBoard().print(nowFmt);

    displayBatteryStatus(batteryRemainingPercent, true);

    epdBoard().display();
}

void displayBatteryStatus(int batteryRemainingPercent, bool invert) {
    // PS apologies for all the hackiness here...
    char msg[5];
    snprintf(msg, sizeof(msg), "%d%%", batteryRemainingPercent);
    epdBoard().setFont(&Merienda_Regular12pt7b);
    epdBoard().setTextSize(1);
    if (invert) {
        epdBoard().setTextColor(0xFF);
    } else {
        epdBoard().setTextColor(0x00);
    }

    int16_t tX, tY;
    uint16_t tW, tH;
    epdBoard().getTextBounds(msg, epdBoard().getHeight() * 0.9, batteryIconSize, &tX, &tY, &tW,
                        &tH);
    // who knows why 0.75 but that lines things up
    epdBoard().setCursor(tX, tY + tH * 0.75);
    epdBoard().print(msg);

    // epdBitmapBatteryFull
    int idx;
    if (batteryRemainingPercent > 66 && batteryRemainingPercent <= 100) {
        idx = 0;
    } else if (batteryRemainingPercent > 33 && batteryRemainingPercent <= 66) {
        // epdBitmapBatteryHalf
        idx = 1;
    } else if (batteryRemainingPercent > 10 && batteryRemainingPercent <= 33) {
        // epdBitmapBatteryLow
        idx = 2;
    } else {
        // epdBitmapBatteryEmpty
        idx = 3;
    }

    uint8_t* buf;
    if (invert) {
        buf = epdBitmapAllInverted[idx];
    } else {
        buf = epdBitmapAll[idx];
    }

    // Draw battery icon bitmap.
    // BLACK and WHITE are the Inkplate driver's, and they are not the same
    // values on every panel it supports, so this stays with the project that
    // knows which panel it has.
    if (!epdBoard().drawBitmap(buf, tX - batteryIconSize, tY - tH / 2,
                          batteryIconSize, batteryIconSize, BLACK, WHITE)) {
        log(LOG_WARNING, "Failed to draw the battery icon");
    }
}
