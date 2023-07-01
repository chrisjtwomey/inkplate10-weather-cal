#include "file_utils.h"
#include <Inkplate.h>
#include <Inkplate.h>
#include <ArduinoJson.h>
#include <ArduinoYaml.h>
#include <StreamUtils.h>
#include <SdFat.h>

#include "log_utils.h"

// The Inkplate board driver instance.
extern Inkplate board;

/**
  Write a data buffer a file at a given path. Store the file on disk at a given path.

  @param buf the data buffer.
  @param size the size of the file to write.
  @param filePath the path of the file on disk.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EFILEW if number of retries is exceeded without success.
*/

esp_err_t writeFile(uint8_t* buf, int32_t size, const char* filePath) {
    logf(LOG_DEBUG, "writing file to path %s", filePath);
    SdFat sd = board.getSdFat();

    // Write image buffer to SD card
    if (sd.exists(filePath)) {
        sd.remove(filePath);
    }

    File sdfile = sd.open(filePath, FILE_WRITE);
    if (!sdfile) {
        return ESP_ERR_EFILEW;
    }

    sdfile.write(buf, size);
    sdfile.close();

    return ESP_OK;
}