#ifndef __PANEL_H__
#define __PANEL_H__

/**
  What this project draws over its pages, in the fonts it chose.

  epd draws the page and nothing else: which typeface a banner wears, and
  where the battery sits, are this display's decisions, not the library's.
*/

/**
  Draw a message across the top of the panel, over the last page.

  The cached image is restored first, so the banner sits over what was
  showing rather than over white.

  @param msg the message to display.
  @param batteryRemainingPercent shown alongside it.
*/
void displayMessage(const char* msg, int batteryRemainingPercent);

/**
  Draw the battery percentage and its icon in the top-right corner.

  @param invert for drawing over a dark banner rather than over a page.
*/
void displayBatteryStatus(int batteryRemainingPercent, bool invert);

/** Draw the version this image was built from, in the top-left corner. */
void drawClientVersion();

#endif  // __PANEL_H__
