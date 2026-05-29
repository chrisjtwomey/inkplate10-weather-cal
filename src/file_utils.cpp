#include "file_utils.h"

#if defined(USE_SDCARD)
// InkplateBoard.h pulls in Inkplate.h -> SdFat.h, providing the full SdFat
// definition needed by the getSdFat() call site below.
#include "InkplateBoard.h"
#include <ArduinoJson.h>
#include <ArduinoYaml.h>
#include <StreamUtils.h>

#include "log_utils.h"

// The board driver instance.
extern IBoard& board;

/**
  Write a data buffer a file at a given path. Store the file on disk at a given path.

  @param buf the data buffer.
  @param size the size of the file to write.
  @param filePath the path of the file on disk.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_EFILEW if number of retries is exceeded without success.
*/

esp_err_t writeFile(uint8_t* buf, size_t size, const char* filePath) {
    logf(LOG_DEBUG, "writing file to path %s", filePath);
    SdFat &sd = static_cast<InkplateBoard&>(board).getSdFat();

    // Write image buffer to SD card.
    // Use SdFile (not File) and raw SdFat open flags rather than FILE_WRITE —
    // FS.h redefines FILE_WRITE to "w" (const char*) which is incompatible.
    if (sd.exists(filePath)) {
        sd.remove(filePath);
    }

    SdFile sdfile;
    sdfile.open(&sd, filePath, O_WRITE | O_CREAT | O_TRUNC);
    if (!sdfile) {
        return ESP_ERR_EFILEW;
    }

    sdfile.write(buf, size);
    sdfile.close();

    return ESP_OK;
}
#endif