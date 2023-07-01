#ifndef __BATTERY_H__
#define __BATTERY_H__
// Define a battery capacity lookup table as an array of structs
struct BatteryCapacity {
    double voltage;
    int percentage;
};

/**
  Look up battery capacity percentage based on voltage.

  @param voltage the current voltage of the battery.
  @returns the capacity remaining as a percentage integer.
*/
int getBatteryCapacity(double voltage);
#endif