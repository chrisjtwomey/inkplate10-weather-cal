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
uint8_t* downloadFile(const char* url, char* nextRefresh, int32_t* size);
#endif