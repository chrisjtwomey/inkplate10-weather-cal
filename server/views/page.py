"""Base page for this project's views.

``epd_server.page.Page`` does the rendering. This subclass only fixes the
output locations for this repo: HTML goes in ``views/html/`` beside the CSS,
icons and fonts so relative links resolve; PNGs go in ``views/`` where
``server.py`` serves them from.
"""
import os

from epd_server.page import Page as _Page

from .words import CLASSIC, Words

_VIEWS_DIR = os.path.dirname(os.path.realpath(__file__))
HTML_DIR = os.path.join(_VIEWS_DIR, "html")
PNG_DIR = _VIEWS_DIR


PICTURES = ("map", "photos")


class Page(_Page):
    def __init__(self, name, *geometry, picture="map", words: Words = CLASSIC,
                 picture_height: float | None = None, default_picture_height: float | None = None, **kwargs):
        # kwargs lets a caller pass renderer= / quantiser= through unchanged.
        super().__init__(name, *geometry, html_dir=HTML_DIR, png_dir=PNG_DIR, **kwargs)
        self.picture = picture
        self.words = words
        self.picture_height, self.default_picture_height = picture_height, default_picture_height
        if picture == "photos":
            self.requires = (*type(self).requires, "photo_urls")

    def picture_css_variables(self) -> str:
        """The picture area's height in pixels, and how far it grew past the theme's
        default, as CSS custom properties; empty at the default height."""
        if self.picture_height is None or self.picture_height == self.default_picture_height:
            return ""
        grow = self.picture_height - (self.default_picture_height or self.picture_height)
        return f"--picture-height:{self.picture_height:.2f}px;--picture-grow:{grow:.2f}px;"

    def picture_url(self, data) -> str:
        """Today's photo when this page shows photos and one is ready, else the map."""
        page_type = getattr(self, "page_type", self.name)
        if self.picture == "photos" and data.get("photo_urls", {}).get(page_type):
            return data["photo_urls"][page_type]
        return data["map_url"]
