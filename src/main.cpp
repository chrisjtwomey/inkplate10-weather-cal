#include <Arduino.h>
#include <GxEPD2_3C.h>
#include <HTTPClient.h>
#include <NTPClient.h>
#include <Syslog.h>
#include <TimeLib.h>
#include <UMS3.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiUdp.h>

#define ENABLE_GxEPD2_GFX 0
#define uS_TO_S_FACTOR 1000000LL
#define MAX_SLEEP_SECS 60 * 60 * 24  // 24 hours
#define DEFAULT_SLEEP_SECS 60        // if can't determine sleep seconds
#define MAX_ATTEMPTS 3  // num attempts to connect, download, and draw image
#define SLEEP_IF_EARLY true  // sleep instead of attempt if woke early

#define DAILY_WAKE_TIME "08:45:00"  // the time everyday to refresh
#define GMT_OFFSET 1                // +X timezone (eg. GMT+1)

#define WIFI_SSID "XXXX"         // replace with your WiFi SSID
#define WIFI_PASS "XXXX"         // replace with your WiFi password
#define IMAGE_HOST "local.host"  // the image host
#define IMAGE_HOST_PORT 8080
#define IMAGE_HOST_PATH "/homepage.bmp"

#define NTP_HOST "europe.pool.ntp.org"
WiFiUDP udpClient;
NTPClient timeClient(udpClient, NTP_HOST, GMT_OFFSET * 60 * 60, 60000);

#if defined(ARDUINO_PROS3) || defined(ARDUINO_TINYS3)
// UnexpectedMaker TinyS3 + ProS3
#define DEVICE_HOSTNAME "ums3"
#define PIN_BUSY 2   // D2 to EPD BUSY
#define PIN_CS 34    // D8 to EPD CS
#define PIN_RST 5    // D3 to EPD RST
#define PIN_DC 4     // D4 to EPD DC
#define PIN_SCK 36   // SCK to EPD CLK
#define PIN_MOSI 35  // MOSI to EPD DIN
#elif defined(ESP32)
#define DEVICE_HOSTNAME "esp32"
// Waveshare driver board
#define PIN_BUSY 25
#define PIN_CS 15
#define PIN_RST 26
#define PIN_DC 27
#define PIN_SCK 13
#define PIN_MOSI 14
#else
#define DEVICE_HOSTNAME "unknown"
#error "No pin mapping for your board, please update pin mapping"
#endif

#define SYSLOG_HOST IMAGE_HOST  // syslog server same as image host
#define SYSLOG_HOST_PORT 514
#define APP_NAME "eink-cal-client"
Syslog syslog(udpClient, SYSLOG_HOST, SYSLOG_HOST_PORT, DEVICE_HOSTNAME,
              APP_NAME, LOG_KERN);

GxEPD2_3C<GxEPD2_750c_Z08, GxEPD2_750c_Z08::HEIGHT> display(
    GxEPD2_750c_Z08(PIN_CS, PIN_DC, PIN_RST, PIN_BUSY));  // GDEW075Z08 800x480

#define BMP_SIGNATURE 0x4D42
#define MAX_ROW_WIDTH 800                  // for up to 7.5" display 800x480
#define INPUT_BUFFER_PIXELS MAX_ROW_WIDTH  // may affect performance
#define MAX_PALETTE_PIXELS 256             // for depth <= 8

RTC_DATA_ATTR int bootCount = 0;
RTC_DATA_ATTR time_t sleepTime = 0;
RTC_DATA_ATTR time_t wakeTime = 0;
RTC_DATA_ATTR time_t dlTime = 0;
RTC_DATA_ATTR unsigned long sleepSecs = 0;

// up to depth 24
uint8_t input_buffer[3 * INPUT_BUFFER_PIXELS];
// buffer for at least one row of b/w bits
uint8_t output_row_mono_buffer[MAX_ROW_WIDTH / 8];
// buffer for at least one row of color bits
uint8_t output_row_color_buffer[MAX_ROW_WIDTH / 8];
// palette buffer for depth <= 8 b/w
uint8_t mono_palette_buffer[MAX_PALETTE_PIXELS / 8];
// palette buffer for depth <= 8 c/w
uint8_t color_palette_buffer[MAX_PALETTE_PIXELS / 8];

// sleep enables deep sleep for a number of seconds
void sleep();
// get_wake_time returns a time object representing the wake time
time_t get_wake_time();
// get_download_time returns a time object representing the download time
time_t get_download_time();
// read8n reads a 8-bit value from the WiFi client
uint32_t read8n(WiFiClient& client, uint8_t* buffer, int32_t bytes);
// read8n reads a 16-bit value from the WiFi client
uint16_t read16(WiFiClient& client);
// read8n reads a 32-bit value from the WiFi client
uint32_t read32(WiFiClient& client);
// skip reads ahead a number of bytes
uint32_t skip(WiFiClient& client, int32_t bytes);
// showBitmapFrom_HTTP sends the bitmap stream to the E-Ink display
bool showBitmapFrom_HTTP(WiFiClient client, const char* host, const int port,
                         const char* path, int16_t x, int16_t y,
                         bool with_color = true);

void setup() {
    ++bootCount;

    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int connectTimeout = 30;  // 15 seconds
    syslog.log(LOG_INFO, "INFO: WiFi connecting...");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        if (--connectTimeout <= 0) {
            syslog.log(LOG_ERR, "ERROR: WiFi connect timeout");
            sleep();
        }
    }
    // Print the IP address
    syslog.logf(LOG_INFO, "INFO: IP address: %s", WiFi.localIP().toString());

    // configure time
    timeClient.begin();
    timeClient.update();
    setTime(timeClient.getEpochTime());

    syslog.logf(LOG_INFO, "INFO: boot count: %d", bootCount);
    if (sleepTime > 0) {
        syslog.logf(LOG_INFO,
                    "INFO: last sleep time:    %02d:%02d:%02d %02d/%02d/%d",
                    hour(sleepTime), minute(sleepTime), second(sleepTime),
                    day(sleepTime), month(sleepTime), year(sleepTime));
    }

    if (wakeTime > 0) {
        syslog.logf(LOG_INFO,
                    "INFO: expected wake time: %02d:%02d:%02d %02d/%02d/%d",
                    hour(wakeTime), minute(wakeTime), second(wakeTime),
                    day(wakeTime), month(wakeTime), year(wakeTime));
    }

    dlTime = get_download_time();
    syslog.logf(LOG_INFO,
                "INFO: download time:      %02d:%02d:%02d %02d/%02d/%d",
                hour(dlTime), minute(dlTime), second(dlTime), day(dlTime),
                month(dlTime), year(dlTime));

    if (DEVICE_HOSTNAME == "ums3") {
        UMS3 ums3;
        ums3.begin();
        float bvolt = ums3.getBatteryVoltage();
        syslog.logf(LOG_INFO, "INFO: battery voltage: %sv", String(bvolt, 2));

        if (ums3.getVbusPresent()) {
            const char* bstat = (bvolt < 4.0) ? "charging" : "charged";
            syslog.logf(LOG_INFO, "INFO: USB power present - battery %s",
                        bstat);
        } else {
            if (bvolt < 3.1) {
                syslog.log(
                    LOG_ALERT,
                    "ALERT: battery near empty! - sleeping until charged");
                sleep();
            } else if (bvolt < 3.3) {
                syslog.log(LOG_WARNING, "WARNING: battery low, charge soon!");
            } else {
                const char* bstat = (bvolt < 3.6) ? "below" : "above";
                syslog.logf(LOG_INFO, "INFO: battery approx %s 50%% capacity",
                            bstat);
            }
        }
    }

    int earlySeconds = dlTime - now();
    if (earlySeconds > 0 && SLEEP_IF_EARLY) {
        syslog.logf(LOG_WARNING,
                    "WARNING: woke %d seconds before download window, "
                    "returning to sleep",
                    earlySeconds);
        sleep();
    }

    bool ok;
    int attempts = -1;
    WiFiClient client;

    while (!ok && ++attempts < MAX_ATTEMPTS) {
        if (attempts > 0) {
            delay(5000);
        }

        if (!client.connect(IMAGE_HOST, IMAGE_HOST_PORT)) {
            syslog.logf(LOG_ERR, "ERROR: connection to %s:%d failed",
                        IMAGE_HOST, IMAGE_HOST_PORT);
            continue;
        }

        ok = showBitmapFrom_HTTP(client, IMAGE_HOST, IMAGE_HOST_PORT,
                                 IMAGE_HOST_PATH, 0, 0, true);
    }

    client.stop();
    sleep();
}

// showBitmapFrom_HTTP sends the bitmap stream to the E-Ink display from the
// WiFi client connection
bool showBitmapFrom_HTTP(WiFiClient client, const char* host, const int port,
                         const char* path, int16_t x, int16_t y,
                         bool with_color) {
    bool flip = true;  // bitmap is stored bottom-to-top
    uint32_t startTime = millis();

    if ((x >= display.epd2.WIDTH) || (y >= display.epd2.HEIGHT)) {
        syslog.log(LOG_ERR, "ERROR: xy out of bounds");
        return false;
    }

    syslog.logf(LOG_INFO, "INFO: requesting URL: http://%s:%d%s", host, port,
                path);

    client.print(String("GET ") + path + " HTTP/1.1\r\n" + "Host: " + host +
                 "\r\n" + "User-Agent: tinys3\r\n" +
                 "Connection: close\r\n\r\n");

    bool connection_ok = false;
    while (client.connected()) {
        String line = client.readStringUntil('\n');
        if (line.startsWith("HTTP/1.0 200 OK")) {
            connection_ok = true;
        }

        if (line == "\r") {
            break;
        }
    }

    if (!connection_ok) {
        syslog.log(LOG_ERR, "ERROR: non-200 response from host");
        return false;
    }

    uint32_t waitStartTime = millis();
    uint32_t currTime = millis();
    int timeout = 30;  // 30 seconds
    while (!client.available()) {
        currTime = millis();

        if (currTime - waitStartTime >= timeout * 1000) {
            syslog.log(LOG_ERR, "ERROR: timeout waiting for image bytes");
            return false;
        }
        delay(50);
    }

    // Parse BMP header
    uint16_t sig = read16(client);
    if (sig != BMP_SIGNATURE) {
        syslog.logf(LOG_ERR, "ERROR: file signature %h not BMP signature %h",
                    sig, BMP_SIGNATURE);
        return false;
    }

    uint32_t fileSize = read32(client);
    uint32_t creatorBytes = read32(client);
    uint32_t imageOffset = read32(client);  // Start of image data
    uint32_t headerSize = read32(client);
    uint32_t width = read32(client);
    uint32_t height = read32(client);
    uint16_t planes = read16(client);
    uint16_t depth = read16(client);  // bits per pixel
    uint32_t format = read32(client);
    uint32_t bytes_read = 7 * 4 + 3 * 2;  // read so far

    if (planes != 1) {
        syslog.logf(LOG_ERR, "ERROR: unsupported planes: %h", planes);
        return false;
    }

    if ((format != 0) && (format != 3)) {
        syslog.logf(LOG_ERR, "ERROR: unsupported format: %h", format);
        return false;
    }

    syslog.logf(LOG_INFO, "INFO: file size: %d", fileSize);
    syslog.logf(LOG_INFO, "INFO: image Offset: %d", imageOffset);
    syslog.logf(LOG_INFO, "INFO: header size: %d", headerSize);
    syslog.logf(LOG_INFO, "INFO: bit depth: %d", depth);
    syslog.logf(LOG_INFO, "INFO: image size: %dx%d", width, height);

    // BMP rows are padded (if needed) to 4-byte boundary
    uint32_t rowSize = (width * depth / 8 + 3) & ~3;
    if (depth < 8) {
        rowSize = ((width * depth + 8 - depth) / 8 + 3) & ~3;
    }

    if (height < 0) {
        height = -height;
        flip = false;
    }

    uint16_t w = width;
    uint16_t h = height;
    if ((x + w - 1) >= display.epd2.WIDTH) {
        w = display.epd2.WIDTH - x;
    }

    if ((y + h - 1) >= display.epd2.HEIGHT) {
        h = display.epd2.HEIGHT - y;
    }

    if (w > MAX_ROW_WIDTH) {
        syslog.logf(LOG_ERR, "ERROR: width %d greater than max row width %d",
                    width, MAX_ROW_WIDTH);
        return false;
    }

    uint8_t bitmask = 0xFF;
    uint8_t bitshift = 8 - depth;
    uint16_t red, green, blue;
    bool whitish, colored;

    if (depth == 1) {
        with_color = false;
    }

    if (depth > 8) {
        syslog.logf(LOG_ERR, "ERROR: unsupported depth %d", depth);
        return false;
    }

    if (depth < 8) {
        bitmask >>= depth;
    }

    bytes_read +=
        skip(client,
             imageOffset - (4 << depth) -
                 bytes_read);  // 54 for regular, diff for colorsimportant

    display.init(115200, true, 2, false);

    for (uint16_t pn = 0; pn < (1 << depth); pn++) {
        blue = client.read();
        green = client.read();
        red = client.read();
        client.read();
        bytes_read += 4;
        whitish = with_color ? ((red > 0x80) && (green > 0x80) && (blue > 0x80))
                             : ((red + green + blue) > 3 * 0x80);  // whitish
        colored = (red > 0xF0) ||
                  ((green > 0xF0) && (blue > 0xF0));  // reddi sh or yellowish?

        if (pn % 8 == 0) {
            mono_palette_buffer[pn / 8] = 0;
            color_palette_buffer[pn / 8] = 0;
        }

        mono_palette_buffer[pn / 8] |= whitish << pn % 8;
        color_palette_buffer[pn / 8] |= colored << pn % 8;
    }

    display.clearScreen();

    uint32_t rowPosition =
        flip ? imageOffset + (height - h) * rowSize : imageOffset;
    bytes_read += skip(client, rowPosition - bytes_read);

    for (uint16_t row = 0; row < h; row++, rowPosition += rowSize) {
        if (!connection_ok || !(client.connected() || client.available())) {
            break;
        }
        delay(1);  // yield() to avoid WDT

        uint32_t in_remain = rowSize;
        uint32_t in_idx = 0;
        uint32_t in_bytes = 0;
        uint8_t in_byte = 0;            // for depth <= 8
        uint8_t in_bits = 0;            // for depth <= 8
        uint8_t out_byte = 0xFF;        // white (for w%8!=0 border)
        uint8_t out_color_byte = 0xFF;  // white (for w%8!=0 border)
        uint32_t out_idx = 0;

        for (uint16_t col = 0; col < w; col++) {
            yield();

            if (!connection_ok || !(client.connected() || client.available())) {
                break;
            }

            // Time to read more pixel data?
            if (in_idx >= in_bytes) {  // ok, exact match for 24bit,  also (size
                                       // IS multiple of 3)
                uint32_t get = in_remain > sizeof(input_buffer)
                                   ? sizeof(input_buffer)
                                   : in_remain;
                uint32_t got = read8n(client, input_buffer, get);

                while ((got < get) && connection_ok) {
                    uint32_t gotmore =
                        read8n(client, input_buffer + got, get - got);

                    got += gotmore;
                    connection_ok = gotmore > 0;
                }
                in_bytes = got;
                in_remain -= got;
                bytes_read += got;
            }

            if (!connection_ok) {
                syslog.logf(LOG_ERR, "ERROR: got no more after %d bytes read!",
                            bytes_read);
                break;
            }

            switch (depth) {
                case 24:
                    blue = input_buffer[in_idx++];
                    green = input_buffer[in_idx++];
                    red = input_buffer[in_idx++];

                    whitish =
                        with_color
                            ? ((red > 0x80) && (green > 0x80) && (blue > 0x80))
                            : ((red + green + blue) > 3 * 0x80);  // whitish

                    colored = (red > 0xF0) ||
                              ((green > 0xF0) &&
                               (blue > 0xF0));  // reddish or yellowish?
                    break;
                case 16: {
                    uint8_t lsb = input_buffer[in_idx++];
                    uint8_t msb = input_buffer[in_idx++];
                    if (format == 0) {  // 555
                        blue = (lsb & 0x1F) << 3;
                        green = ((msb & 0x03) << 6) | ((lsb & 0xE0) >> 2);
                        red = (msb & 0x7C) << 1;
                    } else {  // 565
                        blue = (lsb & 0x1F) << 3;
                        green = ((msb & 0x07) << 5) | ((lsb & 0xE0) >> 3);
                        red = (msb & 0xF8);
                    }
                    whitish =
                        with_color
                            ? ((red > 0x80) && (green > 0x80) && (blue > 0x80))
                            : ((red + green + blue) > 3 * 0x80);  // whitish
                    colored = (red > 0xF0) ||
                              ((green > 0xF0) &&
                               (blue > 0xF0));  // reddish or yellowish?
                } break;
                case 1:
                case 4:
                case 8: {
                    if (in_bits == 0) {
                        in_byte = input_buffer[in_idx++];
                        in_bits = 8;
                    }
                    uint16_t pn = (in_byte >> bitshift) & bitmask;
                    whitish = mono_palette_buffer[pn / 8] & (0x1 << pn % 8);
                    colored = color_palette_buffer[pn / 8] & (0x1 << pn % 8);
                    in_byte <<= depth;
                    in_bits -= depth;
                } break;
            }

            if (whitish) {
                // keep white
            } else if (colored && with_color) {
                out_color_byte &= ~(0x80 >> col % 8);  // colored
            } else {
                out_byte &= ~(0x80 >> col % 8);  // black
            }
            if ((7 == col % 8) ||
                (col == w - 1)) {  // write that last byte! (for w%8!=0 border)
                output_row_color_buffer[out_idx] = out_color_byte;
                output_row_mono_buffer[out_idx++] = out_byte;
                out_byte = 0xFF;        // white (for w%8!=0 border)
                out_color_byte = 0xFF;  // white (for w%8!=0 border)
            }
        }  // end pixel

        int16_t yrow = y + (flip ? h - row - 1 : row);
        display.writeImage(output_row_mono_buffer, output_row_color_buffer, x,
                           yrow, w, 1);

    }  // end line
    syslog.logf(LOG_INFO, "INFO: downloaded in %d seconds",
                (millis() - startTime) / 1000);

    display.refresh();

    syslog.logf(LOG_INFO, "INFO: bytes read: %d", bytes_read);

    return true;
}

// sleep enables deep sleep for a number of seconds
void sleep() {
    wakeTime = get_wake_time();

    if (wakeTime == (time_t)(-1)) {
        syslog.logf(LOG_WARNING, "WARNING: using default sleep %d seconds",
                    DEFAULT_SLEEP_SECS);
        sleepSecs = DEFAULT_SLEEP_SECS;
    } else {
        // set the seconds to sleep for
        sleepSecs = wakeTime - now();
    }

    syslog.logf(LOG_DEBUG,
                "DEBUG: setting deep sleep timer wakeup for %d seconds",
                sleepSecs);

    esp_err_t err = esp_sleep_enable_timer_wakeup(sleepSecs * uS_TO_S_FACTOR);
    if (err == ESP_ERR_INVALID_ARG) {
        syslog.logf(LOG_WARNING,
                    "WARNING: overflow or invalid range for sleep %lu",
                    sleepSecs * uS_TO_S_FACTOR);
        syslog.logf(LOG_WARNING, "WARNING: using default sleep %d seconds",
                    DEFAULT_SLEEP_SECS);
        esp_sleep_enable_timer_wakeup(DEFAULT_SLEEP_SECS * uS_TO_S_FACTOR);
    }
    syslog.logf(LOG_ALERT,
                "ALERT: deep sleeping until %02d:%02d:%02d %02d/%02d/%d",
                hour(wakeTime), minute(wakeTime), second(wakeTime),
                day(wakeTime), month(wakeTime), year(wakeTime));

    delay(1000);
    sleepTime = now();
    Serial.flush();
    esp_deep_sleep_start();
}

// get_wake_time returns a time object representing the wake time
time_t get_wake_time() {
    timeStatus_t status = timeStatus();
    if (status == timeNotSet || status == timeNeedsSync) {
        syslog.log(LOG_ERR, "ERROR: time not set - can't determine wake time");
        return (time_t)(-1);
    }

    time_t nowTime = now();
    unsigned long seconds = dlTime - nowTime;

    if (seconds >= MAX_SLEEP_SECS) {
        seconds = MAX_SLEEP_SECS;
    }

    return nowTime + seconds;
}

// get_download_time returns a time object representing the download time
time_t get_download_time() {
    timeStatus_t status = timeStatus();
    if (status == timeNotSet || status == timeNeedsSync) {
        syslog.log(LOG_ERR,
                   "ERROR: time not set - can't determine download time");
        return (time_t)(-1);
    }

    tmElements_t tm;
    int hr, min, sec;
    sscanf(DAILY_WAKE_TIME, "%d:%d:%d", &hr, &min, &sec);

    tm.Hour = hr;
    tm.Minute = min;
    tm.Second = sec;
    tm.Day = day();
    tm.Month = month();
    tm.Year = CalendarYrToTm(year());

    time_t dlTime = makeTime(tm);
    time_t nowTime = now();

    // rollover to tomorrow
    if (nowTime > dlTime) {
        dlTime += SECS_PER_DAY;
    }

    return dlTime;
}

// read8n reads a 8-bit value from the WiFi client
uint32_t read8n(WiFiClient& client, uint8_t* buffer, int32_t bytes) {
    int32_t remain = bytes;
    uint32_t start = millis();
    while ((client.connected() || client.available()) && (remain > 0)) {
        if (client.available()) {
            int16_t v = client.read();
            *buffer++ = uint8_t(v);
            remain--;
        } else
            delay(1);
        if (millis() - start > 2000) break;  // don't hang forever
    }
    return bytes - remain;
}

// read16 reads a 16-bit value from the WiFi client
uint16_t read16(WiFiClient& client) {
    // BMP data is stored little-endian, same as Arduino.
    uint16_t result;
    ((uint8_t*)&result)[0] = client.read();  // LSB
    ((uint8_t*)&result)[1] = client.read();  // MSB
    return result;
}

// read32 reads a 32-bit value from the WiFi client
uint32_t read32(WiFiClient& client) {
    // BMP data is stored little-endian, same as Arduino.
    uint32_t result;
    ((uint8_t*)&result)[0] = client.read();  // LSB
    ((uint8_t*)&result)[1] = client.read();
    ((uint8_t*)&result)[2] = client.read();
    ((uint8_t*)&result)[3] = client.read();  // MSB
    return result;
}

// skip reads ahead a number of bytes
uint32_t skip(WiFiClient& client, int32_t bytes) {
    int32_t remain = bytes;
    uint32_t start = millis();
    while ((client.connected() || client.available()) && (remain > 0)) {
        if (client.available()) {
            int16_t v = client.read();
            remain--;
        } else
            delay(1);
        if (millis() - start > 2000) break;  // don't hang forever
    }
    return bytes - remain;
}

void loop() {}