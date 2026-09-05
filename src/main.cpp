#include "InkplateBoard.h"
#include "app.h"

// The board. Swap InkplateBoard for another IBoard to run on other hardware.
static InkplateBoard inkplateBoard;
IBoard& board = inkplateBoard;

// Everything a wake does is run_app(), in app.cpp. It is there and not here
// because the tests compile app.cpp on the host against a MockBoard, and this
// file cannot follow them: it names the Inkplate driver, which only builds
// for the ESP32. See test/test_integration.
void setup() { run_app(); }

void loop() {}
