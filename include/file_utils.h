#ifndef __FILE_H__
#define __FILE_H__
#include "error_utils.h"
// The path on SD card where calendar images are downloaded to and read from.
#define CALENDAR_RW_PATH "/calendar.png"
// The file path on SD card to load config.
#define CONFIG_FILE_PATH "/config.yaml"

/**
  Write a data buffer a file at a given path. Store the file on disk at a given path.

  @param buf the data buffer.
  @param size the size of the file to write.
  @param filePath the path of the file on disk.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EFILEW if number of retries is exceeded without success.
*/
esp_err_t writeFile(uint8_t* buf, size_t size, const char* filePath);
#endif