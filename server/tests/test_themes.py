"""The page types and themes (views/themes.py), and each theme's picture area mark."""
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


@pytest.mark.parametrize("theme, page_type", [(n, t) for n, th in THEMES.items() for t in th.pages])
def test_each_page_marks_one_picture_area(theme, page_type):
    with freeze_time("2026-11-13 09:00:00"):
        weather = create("mock", location="Cork", num_hours=6, metric=True)
        data = {name: fetch() for name, fetch in weather.datasets().items()}
        data["map_url"] = "map.png"
        page = page_class(theme, page_type)(825, 1200)
        page.template(**{k: data[k] for k in page.requires})
    areas = BeautifulSoup(str(page.airium), "html.parser").select("[data-picture]")
    assert [a["data-picture"] for a in areas] == ["main"]
    assert areas[0].find("img")["src"] == "map.png"
