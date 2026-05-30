#include "InkplateBoard.h"
#include "app.h"

// Board driver — swap InkplateBoard for another IBoard implementation to
// support different hardware.
static InkplateBoard inkplateBoard;
IBoard& board = inkplateBoard;

void setup() {
    run_app();
}

void loop() {}
