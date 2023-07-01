#ifndef __LOG_H__
#define __LOG_H__
#include "error_utils.h"
#include "time_utils.h"

// Enum of log verbosity levels.
#define LOG_CRIT 0
#define LOG_ERROR 1
#define LOG_WARNING 2
#define LOG_NOTICE 3
#define LOG_INFO 4
#define LOG_DEBUG 5
#ifndef LOG_LEVEL
// Debug logging by default.
#define LOG_LEVEL LOG_DEBUG
#endif

// log message entry history size
#define LOG_QUEUE_MAX_ENTRIES 10

/**
  Connect to a MQTT broker for remote logging.

  @param broker the hostname of the MQTT broker.
  @param port the port of the MQTT broker.
  @param topic the topic to publish logs to.
  @param clientID the name of the logger client to appear as.
  @param max_retries the number of connection attempts to make before fallback
  to serial-only logging.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
esp_err_t configureMQTT(const char* broker, int port, const char* topic,
                        const char* clientID, int max_retries);

/**
  Log a message.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param msg the message to log.
*/
void log(uint16_t pri, const char* msg);

/**
  Log a message with formatting.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param fmt the format of the log message
*/
void logf(uint16_t pri, const char* fmt, ...);

/**
  Converts a priority into a log level prefix.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @returns the string value of the priority.
*/
const char* msgPrefix(uint16_t pri);

/**
  Ensure log queue is populated/emptied based on MQTT connection.

  @param msg the log message
*/
void ensureQueue(char* msg);
#endif