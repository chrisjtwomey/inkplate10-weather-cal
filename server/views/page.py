"""Base page for this project's views.

``epd_server.page.Page`` does the rendering. This subclass only fixes the
output locations for this repo: HTML goes in ``views/html/`` beside the CSS,
icons and fonts so relative links resolve; PNGs go in ``views/`` where
``server.py`` serves them from.
"""
import os

from epd_server.page import Page as _Page

_VIEWS_DIR = os.path.dirname(os.path.realpath(__file__))
HTML_DIR = os.path.join(_VIEWS_DIR, "html")
PNG_DIR = _VIEWS_DIR


PICTURES = ("map", "photos")
# The picture area on each kind of page, as simplified.css and styles.css set it:
# the box's height, and where in it the square's centre sits.
WIDE_HEIGHT_OF_WIDTH, WIDE_CENTRE = 0.606061, 0.30     # today, current, tomorrow
TALL_HEIGHT_OF_HEIGHT, TALL_CENTRE = 0.55, 0.50        # hourly, daily


def picture_windows(inner_width: int, inner_height: int, size: int = 1200) -> dict:
    """The part of the picture's square that each kind of page shows, as
    ``(left, top, right, bottom)`` in the square's pixels."""
    left, right = size / 2 - inner_width / 2, size / 2 + inner_width / 2
    wide = WIDE_HEIGHT_OF_WIDTH * inner_width
    tall = TALL_HEIGHT_OF_HEIGHT * inner_height
    return {
        "wide": (left, size / 2 - WIDE_CENTRE * wide, right, size / 2 + (1 - WIDE_CENTRE) * wide),
        "tall": (left, size / 2 - TALL_CENTRE * tall, right, size / 2 + (1 - TALL_CENTRE) * tall),
    }


class Page(_Page):
    def __init__(self, name, *geometry, picture="map", **kwargs):
        # kwargs lets a caller pass renderer= / quantiser= through unchanged.
        super().__init__(name, *geometry, html_dir=HTML_DIR, png_dir=PNG_DIR, **kwargs)
        self.picture = picture
        if picture == "photos":
            self.requires = (*type(self).requires, "photo_url")

    def picture_url(self, data) -> str:
        """Today's photo when this page shows photos and one is ready, else the map."""
        if self.picture == "photos" and data.get("photo_url"):
            return data["photo_url"]
        return data["map_url"]
