#include "display_utils.h"
#include <Inkplate.h>
#include "icon/icons_32x32.h"
#include "font/Merienda_Regular12pt7b.h"
#include "font/Merienda_Regular16pt7b.h"

#include "log_utils.h"

// The Inkplate board driver instance.
extern Inkplate board;

/**
  Load an image to the display buffer.

  @param filePath the path of the file on disk.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t loadImage(const char* filePath) {
    logf(LOG_INFO, "drawing image from path: %s", filePath);

    if (!board.drawImage(filePath, 0, 0, false, true)) {
        return ESP_ERR_EDRAW;
    }

    return ESP_OK;
}

/**
  Load a PNG image to the display buffer from a data buffer.

  @param buf the data buffer of png.
  @param len the size of buffer.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t loadImage(uint8_t* buf, int32_t len) {
    log(LOG_INFO, "drawing image from buffer");

    if (!board.drawPngFromBuffer(buf, len, 0, 0, false, true)) {
        return ESP_ERR_EDRAW;
    }

    return ESP_OK;
}

/**
  Load a BMP image to the display buffer.

  @param buf the byte array buffer.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t loadImage(uint8_t* buf, int x, int y, int w, int h) {
    log(LOG_DEBUG, "drawing image from byte array...");

    if (!board.drawImage(buf, x, y, w, h, BLACK, WHITE)) {
        return ESP_ERR_EDRAW;
    }

    return ESP_OK;
}

/**
  Draw an message to the display. The error message is drawn in the top-left
  corner of the display. Error message will overlay previously drawn image.

  @param msg the message to display.
  error.
*/
void displayMessage(const char* msg, int batteryRemainingPercent) {
    board.clearDisplay();

#if defined(USE_SDCARD)
    // If previous image exists, load into board buffer.
    esp_err_t err = loadImage(CALENDAR_RW_PATH);
    if (err != ESP_OK) {
        log(LOG_WARNING, "load previous image error");
    }
#endif

    int cX = E_INK_HEIGHT / 2;
    int cY = 16;  // 16pt font
    int16_t x, y;
    uint16_t w, h;
    board.setFont(&Merienda_Regular16pt7b);
    board.setTextSize(1);
    board.setTextColor(BLACK);
    board.setTextWrap(true);
    board.getTextBounds(msg, 0, 0, &x, &y, &w, &h);
    board.fillRect(0, 0, E_INK_HEIGHT, h * 2.5, 0x8080);
    board.setCursor(cX - w / 2, cY + h * 1.5);
    board.setTextColor(0xFFFF);
    board.print(msg);

    String nowFmt = nowTzFmt();
    board.setFont(&Merienda_Regular12pt7b);
    board.setCursor(12, 24);
    board.print(nowFmt);

    displayBatteryStatus(batteryRemainingPercent, true);

    board.display();
}

/**
  Draw the battery status to the display.

  @param batteryRemainingPercent the percentage capacity remaining in the
  battery. error.
*/
void displayBatteryStatus(int batteryRemainingPercent, bool invert) {
    // PS apologies for all the hackiness here...
    char msg[4];
    sprintf(msg, "%d%%", batteryRemainingPercent);
    board.setFont(&Merienda_Regular12pt7b);
    board.setTextSize(1);
    if (invert) {
        board.setTextColor(0xFF);
    } else {
        board.setTextColor(0x00);
    }

    int16_t tX, tY;
    uint16_t tW, tH;
    board.getTextBounds(msg, E_INK_HEIGHT * 0.9, batteryIconSize, &tX, &tY, &tW,
                        &tH);
    // who knows why 0.75 but that lines things up
    board.setCursor(tX, tY + tH * 0.75);
    board.print(msg);

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
    esp_err_t err = loadImage(buf, tX - batteryIconSize, tY - tH / 2,
                              batteryIconSize, batteryIconSize);
    if (err != ESP_OK) {
        log(LOG_WARNING, "Failed to draw epd_bitmap");
    }
}