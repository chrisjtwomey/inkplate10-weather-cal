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


class Page(_Page):
    def __init__(
        self,
        name,
        width,
        height,
        inner_width=None,
        inner_height=None,
        inner_align_x="center",
        inner_align_y="center",
        **kwargs,
    ):
        # kwargs lets a caller pass renderer= / quantiser= through unchanged.
        super().__init__(
            name,
            width,
            height,
            inner_width,
            inner_height,
            inner_align_x,
            inner_align_y,
            html_dir=HTML_DIR,
            png_dir=PNG_DIR,
            **kwargs,
        )
