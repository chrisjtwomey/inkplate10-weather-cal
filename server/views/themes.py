"""The page types and the themes that draw them.

A page type is what a page is for and the data it needs (``Page.requires``);
the display's schedule and sets name page types. A theme is one layout for
some or all of the types, and never changes a type's data.
"""
from dataclasses import dataclass, field

from .current import CurrentPage
from .daily import DailyPage
from .hourly import HourlyPage
from .today import TodayPage
from .tomorrow import TomorrowPage
from .page import picture_windows
from .words import CLASSIC, Words

PAGE_TYPES = ("today", "current", "hourly", "daily", "tomorrow")
DEFAULT_THEME = "classic"


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    pages: dict = field(default_factory=dict)   # page type -> Page class
    words: Words = CLASSIC
    shapes: dict = field(default_factory=dict)  # page type -> its picture area's shape


THEMES = {
    "classic": Theme("classic", "Classic", {
        "today": TodayPage,
        "current": CurrentPage,
        "hourly": HourlyPage,
        "daily": DailyPage,
        "tomorrow": TomorrowPage,
    }, shapes={"today": "wide", "current": "wide", "tomorrow": "wide", "hourly": "tall", "daily": "tall"}),
}


def page_class(theme: str, page_type: str):
    """The class that draws ``page_type`` in ``theme``. Raises KeyError when the
    theme does not exist or has no layout for that type."""
    return THEMES[theme].pages[page_type]


def picture_box(theme: str, page_type: str, inner_width: int, inner_height: int) -> tuple | None:
    """Where ``page_type``'s picture area sits on the picture square in ``theme``,
    as (left, top, right, bottom), or None when the page has no picture area."""
    shape = THEMES[theme].shapes.get(page_type)
    return picture_windows(inner_width, inner_height)[shape] if shape else None
