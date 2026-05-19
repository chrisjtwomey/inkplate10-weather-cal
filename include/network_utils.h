#ifndef __NETWORK_H__
#define __NETWORK_H__
#include "error_utils.h"
/**
  Connect to a WiFi network in Station Mode.

  @param ssid the network SSID.
  @param pass the network password.
  @param retries the number of connection attempts to make before returning an
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
esp_err_t configureWiFi(const char* ssid, const char* pass, int retries);

/**
  Download a file at a given URL. Store the file on disk at a given path.

  @param url the URL of the file to download.
  @param size the size of the file to download.
  @param retries the number of download attempts to make before returning an
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
/**
  Download a file at the given URL.

  If the server sends the X-Next-Refresh-Seconds header, its integer value
  (seconds until the next refresh) is written to `*nextRefreshSeconds`. On a
  missing or malformed header value the out-param is left unmodified.

  If the server sends an X-Next-URL header, up to nextURLSize-1 bytes of the
  value are written into nextURL (null-terminated). Pass nullptr / 0 to ignore.
*/
uint8_t* downloadFile(const char* url, uint32_t* nextRefreshSeconds, int32_t* size,
                      char* nextURL, size_t nextURLSize);
#endif