#ifndef BATTERY_H
#define BATTERY_H

// Define a battery capacity lookup table as an array of structs
struct BatteryCapacity {
    float voltage;
    int percentage;
};

#ifdef BATT_2000MAH
// A capacity table based on a discharge profile over ~50 days.
BatteryCapacity capacityTable[] = {
    {4.25, 100}, {4.19, 98}, {4.15, 96}, {4.12, 94}, {4.1, 91},  {4.08, 89},
    {4.08, 87},  {4.07, 84}, {4.06, 81}, {4.05, 79}, {4.03, 77}, {4, 74},
    {3.98, 72},  {3.96, 70}, {3.95, 68}, {3.94, 66}, {3.93, 64}, {3.92, 62},
    {3.9, 60},   {3.87, 57}, {3.85, 55}, {3.83, 53}, {3.8, 51},  {3.78, 49},
    {3.76, 47},  {3.74, 45}, {3.72, 43}, {3.7, 40},  {3.69, 38}, {3.68, 36},
    {3.67, 34},  {3.65, 32}, {3.64, 30}, {3.62, 27}, {3.6, 23},  {3.57, 21},
    {3.54, 19},  {3.51, 17}, {3.5, 15},  {3.48, 13}, {3.45, 11}, {3.34, 9},
    {3.31, 6},   {3.26, 4},  {3.21, 2},  {3.1, 0},
};
#elif
extern BatteryCapacity capacityTable[];
#endif

const int numCapacityEntries = sizeof(capacityTable) / sizeof(BatteryCapacity);

/**
  Look up battery capacity percentage based on voltage.

  @param voltage the current voltage of the battery.
  @returns the capacity remaining as a percentage integer.
*/
int getBatteryCapacity(float voltage) {
    for (int i = 0; i < numCapacityEntries; i++) {
        if (voltage >= capacityTable[i].voltage) {
            return capacityTable[i].percentage;
        }
    }
    return 0;
}

// 'battery-empty', 32x32px
uint8_t epdBitmapBatteryEmpty[] PROGMEM = {
    0xff, 0xff, 0xff, 0xff, 0xff, 0x60, 0x0,  0x0,  0x0,  0x2,  0xaf, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xf,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xc4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xc2, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x4,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0x4f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf8, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x8,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf2, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf2, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xc,  0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0x20, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x8f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x20, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x2a, 0xff, 0xff, 0xff, 0xff,
};
// 'battery-empty', 32x32px, inverted
uint8_t epdBitmapBatteryEmptyInverted[] PROGMEM = {
    0x0,  0x0,  0x0,  0x0,  0x0,  0x9f, 0xff, 0xff, 0xff, 0xfd, 0x50, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x3b, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x3d, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfb,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xb0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x7,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,  0xd,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,  0xd,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf3, 0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0xdf, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x70, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xdf, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xd5, 0x0,  0x0,  0x0,  0x0,
};
// 'battery-low', 32x32px
uint8_t epdBitmapBatteryLow[] PROGMEM = {
    0xff, 0xff, 0xff, 0xff, 0xff, 0x60, 0x0,  0x0,  0x0,  0x2,  0xaf, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xf,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xc4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xc2, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x4,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0x4f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf8, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x4,  0xaa, 0xaa, 0xaa, 0xaa, 0xaa, 0xa0, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf2, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xc,  0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0x20, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x8f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x20, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x2a, 0xff, 0xff, 0xff, 0xff,
};
// 'battery-low', 32x32px, inverted
uint8_t epdBitmapBatteryLowInverted[] PROGMEM = {
    0x0,  0x0,  0x0,  0x0,  0x0,  0x9f, 0xff, 0xff, 0xff, 0xfd, 0x50, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x3b, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x3d, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfb,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xb0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x7,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xfb, 0x55, 0x55, 0x55, 0x55, 0x55, 0x5f, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,  0xd,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf3, 0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0xdf, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x70, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xdf, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xd5, 0x0,  0x0,  0x0,  0x0,
};
// 'battery-half', 32x32px
uint8_t epdBitmapBatteryHalf[] PROGMEM = {
    0xff, 0xff, 0xff, 0xff, 0xff, 0x60, 0x0,  0x0,  0x0,  0x2,  0xaf, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xf,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xc4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xc2, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x4,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0x4f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf8, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x2,  0x44, 0x44, 0x44, 0x44, 0x44, 0x40, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x8,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf2, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x2,  0x44, 0x44, 0x44,
    0x44, 0x44, 0x40, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf2, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xc,  0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0x20, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x8f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x20, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x2a, 0xff, 0xff, 0xff, 0xff,
};
// 'battery-half', 32x32px, inverted
uint8_t epdBitmapBatteryHalfInverted[] PROGMEM = {
    0x0,  0x0,  0x0,  0x0,  0x0,  0x9f, 0xff, 0xff, 0xff, 0xfd, 0x50, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x3b, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x3d, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfb,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xb0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x7,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xfd, 0xbb, 0xbb, 0xbb, 0xbb, 0xbb, 0xbf, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf7, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xd,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xfd, 0xbb, 0xbb, 0xbb,
    0xbb, 0xbb, 0xbf, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,  0xd,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf3, 0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0xdf, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x70, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xdf, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xd5, 0x0,  0x0,  0x0,  0x0,
};
// 'battery-full', 32x32px
uint8_t epdBitmapBatteryFull[] PROGMEM = {
    0xff, 0xff, 0xff, 0xff, 0xff, 0x60, 0x0,  0x0,  0x0,  0x2,  0xaf, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xf,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xc4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xc2, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x4,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0x4f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf8, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf6, 0x0,  0x2,  0x44, 0x44, 0x44, 0x44, 0x44, 0x40, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x8,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf2, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x2,  0x44, 0x44, 0x44, 0x44, 0x44, 0x40, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x8,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf2, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0x2,  0x44, 0x44, 0x44,
    0x44, 0x44, 0x40, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf4, 0x0,  0xa,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf4, 0x0,  0x8,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf2, 0x0,
    0xa,  0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x0,  0xc,  0xff, 0xff, 0xff, 0xff, 0xff, 0xfa, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xf,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0x20, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x8f, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf6, 0x20, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x2a, 0xff, 0xff, 0xff, 0xff,
};
// 'battery-full', 32x32px, inverted
uint8_t epdBitmapBatteryFullInverted[] PROGMEM = {
    0x0,  0x0,  0x0,  0x0,  0x0,  0x9f, 0xff, 0xff, 0xff, 0xfd, 0x50, 0x0,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff, 0xff, 0xff,
    0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,
    0x3b, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0x3d, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xfb,
    0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xb0, 0x0,  0x0,  0x0,  0x0,  0x0,  0x7,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x9,  0xff, 0xfd, 0xbb, 0xbb, 0xbb, 0xbb, 0xbb, 0xbf, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,  0xd,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xfd, 0xbb, 0xbb, 0xbb, 0xbb, 0xbb, 0xbf, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf7, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xd,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xfd, 0xbb, 0xbb, 0xbb,
    0xbb, 0xbb, 0xbf, 0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0xb,  0xff, 0xf5, 0x0,  0x0,  0x0,
    0x0,  0x0,  0xb,  0xff, 0xf7, 0x0,  0x0,  0x0,  0x0,  0x0,  0xd,  0xff,
    0xf5, 0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xff, 0xff, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xff, 0xf3, 0x0,  0x0,  0x0,  0x0,  0x0,  0x5,  0xff,
    0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xf0, 0x0,  0x0,  0x0,
    0x0,  0x0,  0x0,  0xdf, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff,
    0x70, 0x0,  0x0,  0x0,  0x0,  0x0,  0x0,  0x9,  0xdf, 0xff, 0xff, 0xff,
    0xff, 0xff, 0xff, 0xd5, 0x0,  0x0,  0x0,  0x0,
};

// Array of all bitmaps for convenience. (Total bytes used to store images in
// PROGMEM = 2112)
const int batteryIconSize = 32;
const int epdBitmapAllLen = 4;
uint8_t* epdBitmapAll[4] = {
    epdBitmapBatteryFull,
    epdBitmapBatteryHalf,
    epdBitmapBatteryLow,
    epdBitmapBatteryEmpty,
};
uint8_t* epdBitmapAllInverted[4] = {
    epdBitmapBatteryFullInverted,
    epdBitmapBatteryHalfInverted,
    epdBitmapBatteryLowInverted,
    epdBitmapBatteryEmptyInverted,
};
#endif