"""
HTML structure tests for `TodayPage.template()`.
Verifies that current conditions data is correctly adapted into the day layout.
"""
import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time

from views.today import TodayPage
from weather.mock.mock import MockWeatherService

WIDTH = 825
HEIGHT = 1200

MAP_URL = "https://example.test/staticmap?center=51.9,-8.5"


def _get_current_conditions():
    with freeze_time("2026-05-21 09:00:00"):
        weather = MockWeatherService(metric=True)
        return weather.get_current_conditions()


def _get_daily_summary():
    with freeze_time("2026-05-21 09:00:00"):
        weather = MockWeatherService(metric=True)
        return weather.get_daily_summary()


@pytest.fixture
def current_conditions():
    return _get_current_conditions()


@pytest.fixture
def daily_summary():
    return _get_daily_summary()


@pytest.fixture
def rendered_html(current_conditions, daily_summary):
    with freeze_time("2026-05-21 09:00:00"):
        page = TodayPage(WIDTH, HEIGHT)
        page.template(
            map_url=MAP_URL,
            current_conditions=current_conditions,
            daily_summary=daily_summary,
        )
        return str(page.airium)


def test_html_is_well_formed(rendered_html):
    assert rendered_html.startswith("<!DOCTYPE html>")
    soup = BeautifulSoup(rendered_html, "html.parser")
    assert soup.html is not None
    assert soup.head is not None
    assert soup.body is not None


def test_loads_day_and_today_css(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    hrefs = [link["href"] for link in soup.find_all("link", rel="stylesheet")]
    assert "styles.css" in hrefs
    assert "simplified.css" in hrefs


def test_map_image_uses_provided_url(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    img = soup.find(id="map")
    assert img is not None
    assert img["src"] == MAP_URL


def test_hero_shows_current_temperature(rendered_html, current_conditions):
    soup = BeautifulSoup(rendered_html, "html.parser")
    temp_main = soup.find(id="day-temp-main")
    assert temp_main is not None
    assert str(current_conditions["temperature"]["value"]) in temp_main.get_text()


def test_weather_text_shown_as_phrase(rendered_html, current_conditions):
    soup = BeautifulSoup(rendered_html, "html.parser")
    phrase = soup.find(id="day-phrase")
    assert phrase is not None
    assert current_conditions["weather_text"] in phrase.get_text()


def test_hero_has_icon(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    hero = soup.find(id="day-hero")
    assert hero is not None
    assert hero.find("img", id="day-icon") is not None


def test_date_shown_in_hero(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    date_el = soup.find(id="day-date")
    assert date_el is not None
    text = date_el.get_text()
    assert "Thursday" in text
    assert "21" in text
    assert "May" in text


def test_no_rain_alert_when_probability_is_low():
    """A low rain probability from daily_summary should not trigger a rain alert."""
    cc = _get_current_conditions()
    with freeze_time("2026-05-21 09:00:00"):
        weather = MockWeatherService(metric=True)
        ds = weather.get_daily_summary()
    ds["rain_probability"] = 10  # well below alert threshold

    page = TodayPage(WIDTH, HEIGHT)
    page.template(map_url=MAP_URL, current_conditions=cc, daily_summary=ds)
    soup = BeautifulSoup(str(page.airium), "html.parser")
    alerts_div = soup.find(id="day-alerts")
    if alerts_div:
        texts = [el.get_text().lower() for el in alerts_div.find_all(class_="alert-text")]
        assert not any("rain" in t for t in texts)


def test_no_alerts_when_conditions_mild():
    cc = _get_current_conditions()
    cc["uv_index"] = 2
    cc["wind"] = {"unit": "kmh", "value": 10, "direction_degrees": 0}

    page = TodayPage(WIDTH, HEIGHT)
    page.template(map_url=MAP_URL, current_conditions=cc)
    soup = BeautifulSoup(str(page.airium), "html.parser")
    assert soup.find(id="day-alerts") is None
