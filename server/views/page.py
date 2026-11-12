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
