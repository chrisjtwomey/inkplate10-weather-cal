"""
HTML structure check for `TomorrowPage.template()`.

We feed mock weather data into the template, then serialize the underlying
`airium` document and assert its structure with BeautifulSoup. Selenium /
Chromium rendering is *not* invoked here — that's covered by the end-to-end
docker run separately.
"""
import datetime as dt

import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time

from views.tomorrow import TomorrowPage
from weather.mock.mock import MockWeatherService

WIDTH = 825
HEIGHT = 1200


def _get_tomorrow_forecast():
    """Return the tomorrow entry from the mock 5-day forecast."""
    with freeze_time("2026-05-19 09:00:00"):
        weather = MockWeatherService(metric=True)
        forecasts = weather.get_5day_forecast()
    # index 1 = tomorrow when frozen at 2026-05-19
    return forecasts[1]


@pytest.fixture
def tomorrow_forecast():
    return _get_tomorrow_forecast()


@pytest.fixture
def rendered_html(tomorrow_forecast):
    """Render the tomorrow template and return the HTML string."""
    with freeze_time("2026-05-19 09:00:00"):
        page = TomorrowPage(WIDTH, HEIGHT)
        page.template(
            map_url="https://example.test/staticmap?center=51.9,-8.5",
            tomorrow_forecast=tomorrow_forecast,
        )
        return str(page.airium)


def test_html_is_well_formed(rendered_html):
    assert rendered_html.startswith("<!DOCTYPE html>")
    soup = BeautifulSoup(rendered_html, "html.parser")
    assert soup.html is not None
    assert soup.head is not None
    assert soup.body is not None


def test_inner_canvas_wrapper_and_layout_variables_present(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    outer = soup.find("div", class_="inner-canvas-outer")
    inner = soup.find("div", class_="inner-canvas")
    assert outer is not None
    assert inner is not None
    assert inner.find(id="day-map-wrapper") is not None
    assert "--outer-width:825px" in soup.body.get("style", "")
    assert "--outer-height:1200px" in soup.body.get("style", "")


def test_top_banner_shows_tomorrow_date(rendered_html):
    """Date is rendered inside the hero section in tomorrow-body."""
    soup = BeautifulSoup(rendered_html, "html.parser")

    # No floating header over the map
    assert soup.find(id="tomorrow-header") is None
    assert soup.find(id="tomorrow-label") is None

    # Date is inside the hero
    hero = soup.find(id="day-hero")
    assert hero is not None
    date_el = hero.find(id="day-date")
    assert date_el is not None
    date_text = date_el.get_text(strip=True)
    # Frozen at 2026-05-19, so tomorrow is Wednesday 20 May
    assert "Wednesday" in date_text
    assert "20" in date_text
    assert "May" in date_text


def test_no_floating_date_on_map(rendered_html):
    """No numcircle overlays — no top-banner, temp, or icon-container."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    assert soup.find(id="top-banner") is None
    assert soup.find(id="temp") is None
    assert soup.find(id="icon-container") is None


def test_map_image_uses_provided_url(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    img = soup.find(id="map")
    assert img is not None
    assert img["src"] == "https://example.test/staticmap?center=51.9,-8.5"


def test_phrase_section_present_when_phrases_available(rendered_html, tomorrow_forecast):
    """Mock service always provides phrases, so the hero phrase should render."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    hero = soup.find(id="day-hero")
    assert hero is not None
    assert soup.find(id="day-phrase") is not None
    # night-phrase has been removed from the template
    assert soup.find(id="night-phrase") is None


def test_hero_shows_temp_and_icon(rendered_html, tomorrow_forecast):
    soup = BeautifulSoup(rendered_html, "html.parser")
    hero = soup.find(id="day-hero")
    assert hero is not None

    # Large temperature value in the hero
    temp_main = soup.find(id="day-temp-main")
    assert temp_main is not None
    assert str(tomorrow_forecast["temperature"]["max"]) in temp_main.get_text()

    # Weather icon inside hero
    assert hero.find("img", id="day-icon") is not None


def test_no_phrase_section_when_phrases_absent(rendered_html):
    """When both phrases are None the phrase elements should not be rendered."""
    fc = _get_tomorrow_forecast()
    fc["day_phrase"] = None
    fc["night_phrase"] = None

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find(id="day-phrase") is None
    assert soup.find(id="night-phrase") is None


def test_no_alerts_when_nothing_exceeds_threshold():
    fc = _get_tomorrow_forecast()
    fc["rain_probability"] = 20
    fc["uv_index"] = 3
    fc["wind"]["value"] = 20
    fc["wind"]["unit"] = "kmh"
    fc["pollen"] = None  # ensure no pollen alert fires

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find(id="day-alerts") is None


def test_pollen_alert_absent_when_all_low():
    fc = _get_tomorrow_forecast()
    fc["rain_probability"] = 5
    fc["uv_index"] = 2
    fc["wind"]["value"] = 10
    fc["wind"]["unit"] = "kmh"
    fc["pollen"] = [
        {"name": "Grass", "category": "Low", "category_value": 1},
        {"name": "Tree", "category": "Low", "category_value": 1},
        {"name": "Ragweed", "category": "Low", "category_value": 1},
    ]

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    soup = BeautifulSoup(str(page.airium), "html.parser")
    assert soup.find(id="day-alerts") is None


def test_pollen_alert_absent_when_pollen_is_none():
    fc = _get_tomorrow_forecast()
    fc["rain_probability"] = 5
    fc["uv_index"] = 2
    fc["wind"]["value"] = 10
    fc["wind"]["unit"] = "kmh"
    fc["pollen"] = None

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    soup = BeautifulSoup(str(page.airium), "html.parser")
    assert soup.find(id="day-alerts") is None
