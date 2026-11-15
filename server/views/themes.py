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
from .words import CLASSIC, Words

PAGE_TYPES = ("today", "current", "hourly", "daily", "tomorrow")
DEFAULT_THEME = "classic"


# The picture's square, in pixels: the map image and each photo's drawing.
SQUARE = 1200
PICTURE, DETAIL = "picture", "detail"


@dataclass(frozen=True)
class PictureArea:
    """A page's picture area in a theme.

    ``kind`` says what the page leads with: PICTURE or DETAIL. The height is a
    share of the page's inner width or height (``of``): ``height`` by default,
    and any from ``smallest`` to ``largest``. ``centre`` is how far down the area
    the picture square's centre sits. The theme's CSS sets the same numbers.
    """
    kind: str
    of: str
    height: float
    smallest: float
    largest: float
    centre: float

    def box(self, inner_width: int, inner_height: int, height: float | None = None) -> tuple:
        """The part of the picture square the area shows, as (left, top, right, bottom)."""
        share = min(max(self.height if height is None else height, self.smallest), self.largest)
        tall = share * (inner_width if self.of == "width" else inner_height)
        left, right = SQUARE / 2 - inner_width / 2, SQUARE / 2 + inner_width / 2
        return left, SQUARE / 2 - self.centre * tall, right, SQUARE / 2 + (1 - self.centre) * tall


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    pages: dict = field(default_factory=dict)   # page type -> Page class
    words: Words = CLASSIC
    areas: dict = field(default_factory=dict)   # page type -> PictureArea


# Classic: simplified.css sets the picture pages' area, styles.css the detail pages'.
CLASSIC_PICTURE = PictureArea(PICTURE, "width", 0.606061, 0.5, 1.0, 0.30)
CLASSIC_DETAIL = PictureArea(DETAIL, "height", 0.55, 0.55, 0.55, 0.50)


THEMES = {
    "classic": Theme("classic", "Classic", {
        "today": TodayPage,
        "current": CurrentPage,
        "hourly": HourlyPage,
        "daily": DailyPage,
        "tomorrow": TomorrowPage,
    }, areas={"today": CLASSIC_PICTURE, "current": CLASSIC_PICTURE, "tomorrow": CLASSIC_PICTURE,
              "hourly": CLASSIC_DETAIL, "daily": CLASSIC_DETAIL}),
}


def page_class(theme: str, page_type: str):
    """The class that draws ``page_type`` in ``theme``. Raises KeyError when the
    theme does not exist or has no layout for that type."""
    return THEMES[theme].pages[page_type]


def picture_box(theme: str, page_type: str, inner_width: int, inner_height: int) -> tuple | None:
    """Where ``page_type``'s picture area sits on the picture square in ``theme``,
    as (left, top, right, bottom), or None when the page has no picture area."""
    area = THEMES[theme].areas.get(page_type)
    return area.box(inner_width, inner_height) if area else None
