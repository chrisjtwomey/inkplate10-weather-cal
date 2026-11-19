"""The page types and themes (views/themes.py), and the contract every theme's page keeps."""
import datetime as dt

import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time

import weather.mock.mock  # noqa: F401  (registers "mock")
from views.themes import DEFAULT_THEME, PAGE_TYPES, THEMES, page_class
from weather.registry import create


def test_classic_draws_every_page_type_and_is_the_default():
    assert DEFAULT_THEME == "classic"
    assert set(THEMES["classic"].pages) == set(PAGE_TYPES)
    assert [page_class("classic", t)(825, 1200).name for t in PAGE_TYPES] == list(PAGE_TYPES)


def test_an_unknown_theme_or_page_type_is_a_key_error():
    with pytest.raises(KeyError):
        page_class("neon", "today")
    with pytest.raises(KeyError):
        page_class("classic", "weekly")


# ---------- The theme contract ----------
# Every theme's page for every type, with sample weather, with the map and with a
# photo, at the default, smallest and largest picture size.

NOW = "2026-11-13 09:00:00"      # a Friday
PLACE = "Cork"
# The day each page type is about: today, except the tomorrow page.
DAY = {"tomorrow": dt.date(2026, 11, 14)}
# Pages whose time is implied: a whole day's forecast. The others show the hour.
TIME_IMPLIED = {"today", "daily", "tomorrow"}
# Pages that show a photo with no place name: Classic's, by design (the map shows
# the place; a photo page has no label for now).
NO_PLACE_ON_PHOTOS = {("classic", t) for t in PAGE_TYPES}


def _sizes(theme, page_type):
    """(picture_height, default_picture_height) pairs to draw the page at."""
    area = THEMES[theme].areas.get(page_type)
    if area is None:
        return [(None, None)]
    default = area.pixels(825, 1100)
    heights = {default, area.pixels(825, 1100, 0), area.pixels(825, 1100, 1000)}
    return [(height, default) for height in sorted(heights)]


CASES = [(theme, page_type, picture, size)
         for theme, th in THEMES.items() for page_type in th.pages
         for picture in ("map", "photos") for size in _sizes(theme, page_type)]


@pytest.fixture(scope="module")
def data():
    with freeze_time(NOW):
        weather = create("mock", location=PLACE, num_hours=6, metric=True)
        found = {name: fetch() for name, fetch in weather.datasets().items()}
    return {**found, "map_url": "map.png", "photo_urls": {t: "photo.png" for t in PAGE_TYPES}}


@pytest.mark.parametrize("theme, page_type, picture, size", CASES,
                         ids=[f"{t}-{p}-{pic}-{s[0] and round(s[0])}" for t, p, pic, s in CASES])
def test_every_page_keeps_the_theme_contract(data, theme, page_type, picture, size):
    page = page_class(theme, page_type)(825, 1200, picture=picture, words=THEMES[theme].words,
                                        picture_height=size[0], default_picture_height=size[1])
    with freeze_time(NOW):
        page.template(**{k: data[k] for k in page.requires})     # its own data only
    soup = BeautifulSoup(str(page.airium), "html.parser")
    text = soup.get_text(" ")
    words = THEMES[theme].words

    areas = soup.select("[data-picture]")
    if page_type in THEMES[theme].areas:
        assert [a["data-picture"] for a in areas] == ["main"]
        assert areas[0].find("img")["src"] == ("photo.png" if picture == "photos" else "map.png")
    else:
        assert areas == []

    day = DAY.get(page_type, dt.date(2026, 11, 13))
    assert str(day.day) in text, f"{page_type} shows no date"
    assert words.weekdays[day.weekday()] in text or words.months[day.month - 1] in text, f"{page_type} shows no date"

    if page_type not in TIME_IMPLIED:
        assert words.hour(dt.datetime(2026, 11, 13, 9)) in text, f"{page_type} shows no time"

    if picture == "photos" and (theme, page_type) not in NO_PLACE_ON_PHOTOS:
        assert PLACE in text, f"{page_type} with a photo shows no place"

    if size[0] is not None and size[0] != size[1]:
        assert f"--picture-height:{size[0]:.2f}px" in soup.body["style"]
