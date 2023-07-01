#ifndef __DISPLAY_H__
#define __DISPLAY_H__
#include "error_utils.h"

// Guestimate file size for PNG image @ 1200x825
#define DEFAULT_BUFFER_SIZE E_INK_WIDTH* E_INK_HEIGHT * 4 + 100

/**
  Load an image to the display buffer.

  @param filePath the path of the file on disk.
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EFILER if writing file to filePath fails.
*/
esp_err_t loadImage(const char* filePath);

/**
  Load a PNG image to the display buffer from a data buffer.

  @param buf the data buffer of png.
  @param len the size of buffer.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t loadImage(uint8_t* buf, int32_t len);

/**
  Load a BMP image to the display buffer.

  @param buf the byte array data
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EDL if download file fails.
  - ESP_ERR_EFILEW if writing file to filePath fails.
*/
esp_err_t loadImage(uint8_t* buf, int x, int y, int w, int h);

/**
  Draw the battery status to the display.

  @param batteryRemainingPercent the percentage capacity remaining in the
  battery. error.
  @param invert flag to invert battery status due to black banner.
*/
void displayBatteryStatus(int batteryRemainingPercent, bool invert);

/**
  Draw an message to the display. The error message is drawn in the top-left
  corner of the display. Error message will overlay previously drawn image.

  @param msg the message to display.
  @param batteryRemainingPercent the percentage remaining battery capacity for
  battery status display. error.
*/
void displayMessage(const char* msg, int batteryRemainingPercent);
#endif