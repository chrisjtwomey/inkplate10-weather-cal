#include "battery.h"

/**
 * The discharge profile of a 3.7v 2000mAh Lithium-Polymer battery.
 * 
 * Capacity tables are only ever a rough approximation based on recording 
 * voltages over time from fully charged to discharged. Profiles are 
 * 
 * The best way to improve accuracy is to record the discharge 
 * profile of your own battery and plug the data in here. I recorded this 
 * table by running this project until the voltage cut-off of 3.1v was reached
 * and calculated percentage capacity based on the number of days it ran for.
 * 
 */
BatteryCapacity capacityTable[] = {
    {4.25, 100}, {4.22, 99}, {4.19, 98}, {4.17, 97}, {4.15, 96}, {4.14, 95},
    {4.12, 94},  {4.11, 93}, {4.10, 91}, {4.09, 90}, {4.08, 89}, {4.08, 88},
    {4.08, 87},  {4.08, 86}, {4.07, 85}, {4.07, 84}, {4.07, 83}, {4.07, 82},
    {4.06, 81},  {4.06, 80}, {4.05, 79}, {4.04, 78}, {4.03, 77}, {4.02, 76},
    {4.00, 74},  {3.99, 73}, {3.98, 72}, {3.97, 71}, {3.96, 70}, {3.96, 69},
    {3.95, 68},  {3.95, 67}, {3.94, 66}, {3.94, 65}, {3.93, 64}, {3.93, 63},
    {3.92, 62},  {3.91, 61}, {3.90, 60}, {3.89, 59}, {3.87, 57}, {3.86, 56},
    {3.85, 55},  {3.84, 54}, {3.83, 53}, {3.82, 52}, {3.80, 51}, {3.79, 50},
    {3.78, 49},  {3.77, 48}, {3.76, 47}, {3.75, 46}, {3.74, 45}, {3.73, 44},
    {3.72, 43},  {3.71, 41}, {3.70, 40}, {3.70, 39}, {3.69, 38}, {3.69, 37},
    {3.68, 36},  {3.68, 35}, {3.67, 34}, {3.66, 33}, {3.65, 32}, {3.65, 31},
    {3.64, 30},  {3.63, 29}, {3.62, 28}, {3.62, 27}, {3.62, 26}, {3.61, 24},
    {3.60, 23},  {3.59, 22}, {3.57, 21}, {3.56, 20}, {3.54, 19}, {3.53, 18},
    {3.51, 17},  {3.51, 16}, {3.50, 15}, {3.49, 14}, {3.48, 13}, {3.47, 12},
    {3.45, 11},  {3.40, 10}, {3.34, 9},  {3.33, 7},  {3.31, 6},  {3.29, 5},
    {3.26, 4},   {3.24, 3},  {3.21, 2},  {3.16, 1},  {3.10, 0},
};

const int numCapacityEntries = sizeof(capacityTable) / sizeof(BatteryCapacity);

/**
  Look up battery capacity percentage based on voltage.

  @param voltage the current voltage of the battery.
  @returns the capacity remaining as a percentage integer.
*/
int getBatteryCapacity(double voltage) {
    for (int i = 0; i < numCapacityEntries; i++) {
        if (voltage >= capacityTable[i].voltage) {
            return capacityTable[i].percentage;
        }
    }
    return 0;
}