#include "log_utils.h"
#include <Arduino.h>
#include <WiFi.h>
#include <cppQueue.h>
#include <PubSubClient.h>
#include <MqttLogger.h>

#include "error_utils.h"

// remote mqtt logger
WiFiClient espClient;
PubSubClient client(espClient);
MqttLogger mqttLogger(client, "", MqttLoggerMode::SerialOnly);
// queue to store messages to publish once mqtt connection is established.
cppQueue logQ(sizeof(char) * 100, LOG_QUEUE_MAX_ENTRIES, FIFO, true);

/**
  Connect to a MQTT broker for remote logging.

  @param broker the hostname of the MQTT broker.
  @param port the port of the MQTT broker.
  @param topic the topic to publish logs to.
  @param clientID the name of the logger client to appear as.
  @param max_retries the number of connection attempts to make before
  fallback to serial-only logging.
  @returns the esp_err_t code:
  - ESP_OK if successful.
  - ESP_ERR_TIMEOUT if number of retries is exceeded without success.
*/
esp_err_t configureMQTT(const char* broker, int port, const char* topic,
                        const char* clientID, int max_retries) {
    log(LOG_INFO, "configuring remote MQTT logging...");

    client.setServer(broker, port);
    // Attempt to connect to MQTT broker.
    int attempts = 0;
    while (attempts++ <= max_retries && !client.connect(clientID)) {
        logf(LOG_DEBUG, "connection attempt #%d...", attempts);
        delay(250);
    }

    if (!client.connected()) {
        return ESP_ERR_TIMEOUT;
    }

    mqttLogger.setTopic(topic);
    mqttLogger.setMode(MqttLoggerMode::MqttAndSerial);

    logf(LOG_INFO, "connected to MQTT broker %s:%d", broker, port);

    return ESP_OK;
}

/**
  Converts a priority into a log level prefix.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @returns the string value of the priority.
*/
const char* msgPrefix(uint16_t pri) {
    char* priority;

    switch (pri) {
        case LOG_CRIT:
            priority = (char*)"CRITICAL";
            break;
        case LOG_ERROR:
            priority = (char*)"ERROR";
            break;
        case LOG_WARNING:
            priority = (char*)"WARNING";
            break;
        case LOG_NOTICE:
            priority = (char*)"NOTICE";
            break;
        case LOG_INFO:
            priority = (char*)"INFO";
            break;
        case LOG_DEBUG:
            priority = (char*)"DEBUG";
            break;
        default:
            priority = (char*)"INFO";
            break;
    }

    char* prefix = new char[35];
    String nowFmt = nowTzFmt();
    sprintf(prefix, "%s - %s - ", nowFmt.c_str(), priority);
    return prefix;
}

/**
  Log a message.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param msg the message to log.
*/
void log(uint16_t pri, const char* msg) {
    if (pri > LOG_LEVEL) return;

    const char* prefix = msgPrefix(pri);
    size_t prefixLen = strlen(prefix);
    size_t msgLen = strlen(msg);
    char buf[prefixLen + msgLen + 1];
    strcpy(buf, prefix);
    strcat(buf, msg);
    ensureQueue(buf);
}

/**
  Log a message with formatting.

  @param pri the log level / priority of the message, see LOG_LEVEL.
  @param fmt the format of the log message
*/
void logf(uint16_t pri, const char* fmt, ...) {
    if (pri > LOG_LEVEL) return;

    const char* prefix = msgPrefix(pri);
    size_t prefixLen = strlen(prefix);
    size_t msgLen = strlen(fmt);
    char a[prefixLen + msgLen + 1];
    strcpy(a, prefix);
    strcat(a, fmt);

    va_list args;
    va_start(args, fmt);
    size_t size = snprintf(NULL, 0, a, args);
    char b[size + 1];
    vsprintf(b, a, args);
    ensureQueue(b);
    va_end(args);
}

/**
  Ensure log queue is populated/emptied based on MQTT connection.

  @param msg the log message.
*/
void ensureQueue(char* logMsg) {
    if (!client.connected()) {
        // populate log queue while no mqtt connection
        logQ.push(logMsg);
    } else {
        // send queued logs once we are connected.
        if (logQ.getCount() > 0) {
            mqttLogger.setMode(MqttLoggerMode::MqttOnly);
            while (!logQ.isEmpty()) {
                logQ.pop(logMsg);
                mqttLogger.println(logMsg);
            }
            mqttLogger.setMode(MqttLoggerMode::MqttAndSerial);
        }
    }
    // print/send the current log
    mqttLogger.println(logMsg);
}