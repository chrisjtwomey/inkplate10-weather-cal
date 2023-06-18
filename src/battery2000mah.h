#ifndef BATTERY_2000MAH_H
#define BATTERY_2000MAH_H
// Define a battery capacity lookup table as an array of structs
struct BatteryCapacity {
    float voltage;
    int percentage;
};

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
#endif