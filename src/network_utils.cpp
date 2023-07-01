#include "network_utils.h"

#include <HTTPClient.h>
#include <WiFi.h>

#include "error_utils.h"
#include "log_utils.h"

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
esp_err_t configureWiFi(const char* ssid, const char* pass, int retries) {
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, pass);
    logf(LOG_INFO, "connecting to WiFi SSID %s...", ssid);

    // Retry until success or give up
    int attempts = 0;
    while (attempts++ <= retries && WiFi.status() != WL_CONNECTED) {
        logf(LOG_DEBUG, "connection attempt #%d...", attempts);
        delay(1000);
    }

    // If still not connected, error with timeout.
    if (WiFi.status() != WL_CONNECTED) {
        return ESP_ERR_TIMEOUT;
    }
    // Print the IP address
    logf(LOG_DEBUG, "IP address: %s", WiFi.localIP().toString());

    return ESP_OK;
}

/**
  Download a file at the given URL to a data buffer.

  If the server also sends X-Next-Refresh header, the value at pointer
  nextRefresh will be populated indicating when to wake up next.

  @param buf the data buffer for the downloaded file.
  @param size the size of the file to download.
  @param url the URL where to download the file.
  @param nextRefresh a pointer storing the next time to refresh / wake up.
  error.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
uint8_t* downloadFile(const char* url, char* nextRefresh, int32_t* defaultLen) {
    logf(LOG_INFO, "downloading file at URL %s", url);

    bool sleep = WiFi.getSleep();
    WiFi.setSleep(false);

    HTTPClient http;
    http.getStream().setNoDelay(true);
    http.getStream().setTimeout(5);

    const char* headersToCollect[] = {
        "X-Next-Refresh",
    };
    const size_t numberOfHeaders = 1;
    http.collectHeaders(headersToCollect, numberOfHeaders);

    // Connect with HTTP
    http.begin(url);

    int httpCode = http.GET();

    int32_t size = http.getSize();
    if (size == -1)
        size = *defaultLen;
    else
        *defaultLen = size;

    uint8_t* buffer = (uint8_t *)ps_malloc(size);
    uint8_t *buffPtr = buffer;

    if (httpCode != HTTP_CODE_OK) {
        logf(LOG_ERROR, "Non-200 response from URL %s: %d", url, httpCode);
        return buffer;
    }

    if (http.hasHeader("X-Next-Refresh")) {
        // Get the next refresh header value from the server.
        // We use this to determine when to wake up next.
        String headerVal = http.header("X-Next-Refresh");
        const char* headerValPtr = headerVal.c_str();
        strcpy(nextRefresh, headerValPtr);
        
        logf(LOG_DEBUG, "received header X-Next-Refresh: %s", nextRefresh);
    } else {
        logf(LOG_WARNING, "header X-Next-Refresh not found in response");
    }

    int32_t total = http.getSize();
    int32_t len = total;

    uint8_t buff[512] = {0};

    WiFiClient* stream = http.getStreamPtr();
    while (http.connected() && (len > 0 || len == -1)) {
        size_t size = stream->available();

        if (size) {
            int c = stream->readBytes(
                buff, ((size > sizeof(buff)) ? sizeof(buff) : size));
            memcpy(buffPtr, buff, c);

            if (len > 0) len -= c;
            buffPtr += c;
        } else if (len == -1) {
            len = 0;
        }
    }

    http.end();
    WiFi.setSleep(sleep);

    return buffer;
}