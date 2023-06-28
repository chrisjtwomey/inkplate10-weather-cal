# Power Consumption

The goal of this page is to document the power consumption performance of this project, findings and improvements along with some plots of voltage curves of performance test runs. This will be formatted like a timeline as I learn about long-term battery performance and ESP32 deep sleep states.

With MQTT remote logging enabled, the client sends a log message to the server with its battery voltage. The server logs include the client MQTT messages which we can use to plot a graph of battery voltage over time.

The client has a cut-off voltage of 3.1v after which normal code execution is no longer allowed. At this point, a notice to recharge is displayed before entering a long deep sleep to protect the battery.

The predictions of battery life when there is a single daily reboot with optimal WiFi connection (line-of-sight, minimal failed connection attempts):
  - **3.7v 2000mAh LiPo/Li-ion @ 0.2C:**
    - Pessimistic: **6 months**
    - Realistic: **1 year**
    - Optimistic: **2+ years**
    - Theoretical: **4+ years**
  - **3.7v 6700mAh Li-ion @ 0.2C:**
    - Pessimistic: **20 months**
    - Realistic: **3+ years**
    - Optimistic: **6+ years**
    - Theoretical: **13+ years**

Keep in mind, these predictions do not take into account the average life span of batteries which may cap these predictions at [2-3 years on average](https://www.newark.com/pdfs/techarticles/tektronix/LIBMG.pdf) nor do they take into account the natural depletion of charge and capacity over time. Expectations of performance should therefore fall somewhere between the pessimistic and optimistic ranges for battery life.

**Note: be sure to check the health of your battery every few months regardless of reported battery percentage.**

## Update June 28 2023

I picked up a [PPK2](https://www.nordicsemi.com/Products/Development-hardware/Power-Profiler-Kit-2) as I wanted to measure deep sleep current draw with the June 20 version of the code:

![sleep](https://user-images.githubusercontent.com/5797356/248981718-ed4f92e4-3e3d-40b8-b4d7-cf3b38c8a948.png)

As you can see, deep sleep current draw is _far_ too high. This explains why the initial test run only lasted 50-ish days. Something was consuming milliamps of power even when we are deep sleeping.

While I initially suspected it to either be my code, or an [ESP32 issue](https://github.com/espressif/arduino-esp32/issues/1113) itself, the problem boiled down to my version of Inkplate10 hardware being old and missing some hardware that sleeps the SD card module and reduces power consumption.

See [the issue in Inkplate's repo](https://github.com/SolderedElectronics/Inkplate-Arduino-library/issues/209) to get the latest updates. Otherwise, for best battery life I recommend you **do not an SD card if you have an E-Radionica Inkplate10**.

I've made an update which makes SD cards **optional**. Once you disable and remove the SD card, deep sleep power consumption returns to **24µA** which theoretically gives this project years of battery life even on small capacity batteries.

## Update June 20 2023

After the first performance test run, and re-analysing client code, there are a number of places where power is unneccesarily consumed:
 - It's possible that the microcontroller is not entering _true deep sleep_ with the advertised 22 µA power consumption. Power consumption currently seems to be closer to 1 mA which is unacceptable. According to [this issue](https://github.com/espressif/arduino-esp32/issues/1113) it's possible the Inkplate recommend method of sleeping/waking up using the RTC might be responsible for the high power consumption.
 - WiFi connects early and stays connected long after it's required - the WiFi radio is by far the largest consumer of power and minimising time using it is crucial.
 - Code unnecessarily refreshes the display with previous day's downloaded image. This was intended for partial update support so if fatal errors occurred  it could be displayed on top of the previous day's calendar image. Code now only refreshes with previous image when there is indeed a fatal error.
 - Code prioritised helpful logging over minimising awake time. This was helpful when tesing and developing but now it's better to turn off remote logging or sleep as soon as it's possible.
 - Storing unnecessary data in RTC memory - while helpful for debugging/testing, it's no longer necessary.

A number of changes have been made around optimising performance and minimising awake time:
 - ~50% less awake time than before, average about 10-15 seconds over the previous ~20-25 seconds
 - 100% less power consumption than before, due to only refreshing the display once and minimising WiFi radio time.

A second series has been added to the graph above which will track the long-term power consumption on the same battery for comparison. Like the last time, I will update the graph every few weeks.

## Update June 18 2023

<img width="800" src="https://github.com/chrisjtwomey/inkplate10-weather-cal/assets/5797356/dae1b40f-39d7-4685-a556-7cbf117b608e" />
  
**Some takeaways:**
  - Current performance is worse than expectations at **47 days**
  - Deep Sleep power consumption is _very_ high - the rate of voltage change each day suggests significant power usage while device is in deep sleep state.
  - Voltage plot does not fit a [typical LiPo/Li-ion voltage curve](https://www.researchgate.net/figure/Typical-discharge-curve-of-a-battery-showing-the-nominal-battery-voltage-which-is_fig1_256454266) - an initial voltage drop is expected, followed by a stabilising around the nominal voltage of 3.7v and then a cliff-like drop off towards the end of capacity.
    - While there are expected dips at the start and end of discharge, the overall rate of voltage drop remains more or less linear.  