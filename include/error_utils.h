#ifndef __ERROR_H__
#define __ERROR_H__
#include <esp_err.h>

// Enum of errors that might be encountered.
#define ESP_ERR_ERRNO_BASE (0)
#define ESP_ERR_EDL (1 + ESP_ERR_ERRNO_BASE)     // Download error
#define ESP_ERR_EDRAW (2 + ESP_ERR_ERRNO_BASE)   // Draw error
#define ESP_ERR_EFILEW (3 + ESP_ERR_ERRNO_BASE)  // File write error
#define ESP_ERR_EFILER (4 + ESP_ERR_ERRNO_BASE)  // File read error
#define ESP_ERR_ENTP (5 + ESP_ERR_ERRNO_BASE)    // NTP error
#endif