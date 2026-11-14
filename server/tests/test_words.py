"""Each theme's words (views/words.py), and that the pages take every word from them."""
import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time

import weather.mock.mock  # noqa: F401  (registers "mock")
from views.themes import PAGE_TYPES, page_class
from views.words import CLASSIC
from weather.registry import create

VIEWS = Path(__file__).parent.parent / "views"


@pytest.mark.parametrize("when, long, short", [
    (dt.date(2026, 11, 13), "Friday, November 13", "13 Nov"),
    (dt.date(2026, 1, 5), "Monday, January 5", "5 Jan"),
])
def test_classic_dates(when, long, short):
    assert (CLASSIC.date_long(when), CLASSIC.date_short(when)) == (long, short)
    assert CLASSIC.month(when) == long.split(", ")[1].split(" ")[0]


@pytest.mark.parametrize("hour, words", [(0, "12am"), (9, "9am"), (12, "12pm"), (23, "11pm")])
def test_classic_hours(hour, words):
    assert CLASSIC.hour(dt.datetime(2026, 11, 13, hour)) == words


def test_classic_terms():
    assert (CLASSIC.percent(36), CLASSIC.rain(36)) == ("36%", "36% rain")
    assert (CLASSIC["kmh"], CLASSIC["hours"], CLASSIC["uv_medium"]) == ("kph", "hours", "Med")


def test_no_view_formats_a_date_with_strftime():
    users = [p.name for p in VIEWS.glob("*.py") if "strftime" in p.read_text() and p.name != "words.py"]
    assert users == []


OTHER = replace(
    CLASSIC,
    weekdays=("Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"),
    weekdays_short=("Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"),
    months=("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
            "novembre", "décembre"),
    months_short=("janv", "févr", "mars", "avr", "mai", "juin", "juil", "août", "sept", "oct", "nov", "déc"),
    patterns={**CLASSIC.patterns, "date_long": "{weekday} {day} {month}", "rain": "{value} % de pluie",
              "percent": "{value} %", "hour": "{hour} h"},
    terms={**CLASSIC.terms, "hours": "heures", "uv_low": "Faible", "uv_medium": "Moyen", "uv_high": "Élevé",
           "kmh": "km/h"},
)


@pytest.mark.parametrize("page_type", PAGE_TYPES)
def test_every_page_takes_its_words_from_the_list(page_type):
    with freeze_time("2026-11-13 09:00:00"):
        weather = create("mock", location="Cork", num_hours=6, metric=True)
        data = {name: fetch() for name, fetch in weather.datasets().items()}
        data["map_url"] = "map.png"
        page = page_class("classic", page_type)(825, 1200, words=OTHER)
        page.template(**{k: data[k] for k in page.requires})
    soup = BeautifulSoup(str(page.airium), "html.parser")
    for phrase in soup.select("#day-phrase"):     # the provider's own words, not the theme's
        phrase.decompose()
    text = soup.get_text(" ")
    for english in ("Friday", "November", "rain", "hours", "kph", " Low", " Med", "High", "am ", "pm "):
        assert english not in text, f"{page_type} shows {english!r}"
    expected = {"today": "Vendredi 13 novembre", "current": "9 h", "hourly": "km/h", "daily": "VEN", "tomorrow": "Samedi 14 novembre"}
    assert expected[page_type] in text
