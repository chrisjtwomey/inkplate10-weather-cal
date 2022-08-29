#define ENABLE_GxEPD2_GFX 0
#define uS_TO_S_FACTOR 1000000LL

#include <Arduino.h>
#include <GxEPD2_3C.h>
#include <HTTPClient.h>
#include <NTPClient.h>
#include <TimeLib.h>
#include <UMS3.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiUdp.h>
#include <secrets.h>

RTC_DATA_ATTR int bootCount = 0;
RTC_DATA_ATTR time_t sleepTime = 0;

const char* IMAGE_HOST = "localhost";
const int IMAGE_HOST_PORT = 8080;
const char* IMAGE_HOST_PATH = "/homepage.bmp";

const int UPDATE_HOUR = 8;     // hour to update in 24hour format
const int UPDATE_MINUTE = 45;  // minute to update
const int UPDATE_SECOND = 0;   // second to update
const int GMT_OFFSET = 1;      // timezone eg. GMT+1

WiFiUDP ntpUDP;
NTPClient timeClient(ntpUDP, "europe.pool.ntp.org", GMT_OFFSET * 60 * 60,
                     60000);

// tinys3/pros3
static const uint8_t EPD_BUSY = 2;   // D2 to EPD BUSY
static const uint8_t EPD_CS = 34;    // D8 to EPD CS
static const uint8_t EPD_RST = 5;    // D3 to EPD RST
static const uint8_t EPD_DC = 4;     // D4 to EPD DC
static const uint8_t EPD_SCK = 36;   // SCK to EPD CLK
static const uint8_t EPD_MOSI = 35;  // MOSI to EPD DIN

static const uint16_t bmp_signature = 0x4D42;
static const uint16_t input_buffer_pixels = 800;  // may affect performance
static const uint16_t max_row_width = 800;  // for up to 7.5" display 800x480
static const uint16_t max_palette_pixels = 256;  // for depth <= 8

GxEPD2_3C<GxEPD2_750c_Z08, GxEPD2_750c_Z08::HEIGHT> display(
    GxEPD2_750c_Z08(/*CS=D8*/ EPD_CS, /*DC=D3*/ EPD_DC, /*RST=D4*/ EPD_RST,
                    /*BUSY=D2*/ EPD_BUSY));  // GDEW075Z08 800x480

// up to depth 24
uint8_t input_buffer[3 * input_buffer_pixels];
// buffer for at least one row of b/w bits
uint8_t output_row_mono_buffer[max_row_width / 8];
// buffer for at least one row of color bits
uint8_t output_row_color_buffer[max_row_width / 8];
// palette buffer for depth <= 8 b/w
uint8_t mono_palette_buffer[max_palette_pixels / 8];
// palette buffer for depth <= 8 c/w
uint8_t color_palette_buffer[max_palette_pixels / 8];

void showBitmapFrom_HTTP(WiFiClient client, const char* host, const int port,
                         const char* path, int16_t x, int16_t y,
                         bool with_color = true);

// Gets the number of seconds until next wake time
unsigned long get_sleep_seconds() {
    timeStatus_t status = timeStatus();
    if (status == timeNotSet || status == timeNeedsSync) {
        Serial.println("Warning: time not set, setting sleep for 60 seconds");
        return 60;
    }

    tmElements_t tm;

    tm.Second = UPDATE_SECOND;
    tm.Hour = UPDATE_HOUR;
    tm.Minute = UPDATE_MINUTE;
    tm.Day = day();
    tm.Month = month();
    tm.Year = year() - 1970;

    time_t then = makeTime(tm);
    time_t nowTime = now();

    // rollover to tomorrow
    if (nowTime > then) {
        then += SECS_PER_DAY;
    }

    return then - nowTime;
}

void sleep() {
    unsigned long sleep_seconds = get_sleep_seconds();

    esp_sleep_enable_timer_wakeup(sleep_seconds * uS_TO_S_FACTOR);
    Serial.println("Deep sleeping for " + String(sleep_seconds) + " seconds");

    Serial.println("Going to sleep now");
    sleepTime = now();
    delay(1000);
    Serial.flush();
    esp_deep_sleep_start();
}

void setup() {
    Serial.begin(9600);
    delay(10000);

    ++bootCount;
    Serial.println("Boot count: " + String(bootCount));

    if (sleepTime > 0) {
        Serial.printf("Last sleep time: %d:%d:%d %d/%d/%d\n" + hour(sleepTime),
                      minute(sleepTime), second(sleepTime), day(sleepTime),
                      month(sleepTime), year(sleepTime));
    }

    display.init(115200, true, 2, false);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int ConnectTimeout = 30;  // 15 seconds
    Serial.print("WiFi connecting");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
        if (--ConnectTimeout <= 0) {
            Serial.println();
            Serial.println("Error: WiFi connect timeout");

            sleep();
        }
    }
    // Print the IP address
    Serial.printf("%s\n", WiFi.localIP().toString());

    // configure time
    timeClient.begin();
    timeClient.update();
    setTime(timeClient.getEpochTime());

    WiFiClient client;
    if (!client.connect(IMAGE_HOST, IMAGE_HOST_PORT)) {
        Serial.println("Error: connection to " + String(IMAGE_HOST) + ":" +
                       String(IMAGE_HOST_PORT) + " failed");
        sleep();
    }

    showBitmapFrom_HTTP(client, IMAGE_HOST, IMAGE_HOST_PORT, IMAGE_HOST_PATH, 0,
                        0, true);

    client.stop();

    sleep();
}

uint16_t read16(WiFiClient& client) {
    // BMP data is stored little-endian, same as Arduino.
    uint16_t result;
    ((uint8_t*)&result)[0] = client.read();  // LSB
    ((uint8_t*)&result)[1] = client.read();  // MSB
    return result;
}

uint32_t read32(WiFiClient& client) {
    // BMP data is stored little-endian, same as Arduino.
    uint32_t result;
    ((uint8_t*)&result)[0] = client.read();  // LSB
    ((uint8_t*)&result)[1] = client.read();
    ((uint8_t*)&result)[2] = client.read();
    ((uint8_t*)&result)[3] = client.read();  // MSB
    return result;
}

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

void showBitmapFrom_HTTP(WiFiClient client, const char* host, const int port,
                         const char* path, int16_t x, int16_t y,
                         bool with_color) {
    bool flip = true;  // bitmap is stored bottom-to-top
    uint32_t startTime = millis();

    if ((x >= display.epd2.WIDTH) || (y >= display.epd2.HEIGHT)) {
        Serial.println("Error: xy out of bounds");
        return;
    }

    UMS3 ums3;
    float bvolt = ums3.getBatteryVoltage();

    Serial.print("requesting URL: ");
    Serial.println(String("http://") + String(host) + ":" + String(port) +
                   path + "?bvolt=" + String(bvolt));

    client.print(String("GET ") + path + "?bvolt=" + String(bvolt) +
                 " HTTP/1.1\r\n" + "Host: " + host + "\r\n" +
                 "User-Agent: tinys3\r\n" + "Connection: close\r\n\r\n");

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
        Serial.println("Error: non-200 response from host");
        return;
    }

    uint32_t waitStartTime = millis();
    uint32_t currTime = millis();
    int timeout = 30;  // 30 seconds
    while (!client.available()) {
        currTime = millis();

        if (currTime - waitStartTime >= timeout * 1000) {
            Serial.println("Error: timeout waiting for image bytes");
            return;
        }
        delay(50);
    }

    // Parse BMP header
    uint16_t sig = read16(client);
    if (sig != bmp_signature) {
        Serial.print("Error: mismatch between bmp signature 0x");
        Serial.print(bmp_signature, HEX);
        Serial.print(" and file signature 0x");
        Serial.print(sig, HEX);
        return;
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
        Serial.println("Error: unsupported planes ");
        Serial.print(planes, HEX);
        return;
    }

    if ((format != 0) && (format != 3)) {
        Serial.println("Error: unsupported format ");
        Serial.print(format, HEX);
        return;
    }

    Serial.print("File size: ");
    Serial.println(fileSize);
    Serial.print("Image Offset: ");
    Serial.println(imageOffset);
    Serial.print("Header size: ");
    Serial.println(headerSize);
    Serial.print("Bit Depth: ");
    Serial.println(depth);
    Serial.print("Image size: ");
    Serial.print(width);
    Serial.print('x');
    Serial.println(height);

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

    if (w > max_row_width) {
        Serial.println("Error: width greater than max row width");
        return;
    }

    uint8_t bitmask = 0xFF;
    uint8_t bitshift = 8 - depth;
    uint16_t red, green, blue;
    bool whitish, colored;

    if (depth == 1) {
        with_color = false;
    }

    if (depth > 8) {
        Serial.println("Error: unsupported depth " + depth);
        return;
    }

    if (depth < 8) {
        bitmask >>= depth;
    }

    bytes_read +=
        skip(client,
             imageOffset - (4 << depth) -
                 bytes_read);  // 54 for regular, diff for colorsimportant

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
                Serial.print("Error: got no more after ");
                Serial.print(bytes_read);
                Serial.println(" bytes read!");
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
    Serial.print("downloaded in ");
    Serial.print((millis() - startTime) / 1000);
    Serial.println(" seconds");

    display.refresh();

    Serial.print("bytes read ");
    Serial.println(bytes_read);

    client.stop();
}

void loop() {}