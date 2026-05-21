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


def test_stats_section_present(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    stats_div = soup.find(id="day-stats")
    assert stats_div is not None
    stat_rows = stats_div.find_all(class_="stat-row")
    # rain and wind always present; UV when available = at least 2
    assert len(stat_rows) >= 2


def test_hero_shows_temp_and_icon(rendered_html, tomorrow_forecast):
    soup = BeautifulSoup(rendered_html, "html.parser")
    hero = soup.find(id="day-hero")
    assert hero is not None

    # Large temperature value in the hero
    temp_main = soup.find(id="day-temp-main")
    assert temp_main is not None
    assert str(tomorrow_forecast["temperature"]["max"]) in temp_main.get_text()

    # Range moved out of the hero — should not appear inside #day-hero
    assert hero.find(id="day-temp-range") is None

    # Weather icon inside hero
    assert hero.find("img", id="day-icon") is not None


def test_temp_range_pill_in_stats_area(rendered_html, tomorrow_forecast):
    soup = BeautifulSoup(rendered_html, "html.parser")

    # Must not be inside the hero
    hero = soup.find(id="day-hero")
    assert hero.find(id="day-temp-range") is None

    # Must exist outside the hero with both temperature labels
    temp_range = soup.find(id="day-temp-range")
    assert temp_range is not None, "#day-temp-range not found"
    range_text = temp_range.get_text()
    assert str(tomorrow_forecast["temperature"]["min"]) in range_text
    assert str(tomorrow_forecast["temperature"]["max"]) in range_text

    # daily-style track + pill divs must be present with inline positioning
    track = temp_range.find("div", class_="temp-bar-track-v")
    assert track is not None, ".temp-bar-track-v not found inside #day-temp-range"
    pill = track.find("div", class_="temp-bar-pill-v")
    assert pill is not None, ".temp-bar-pill-v not found inside .temp-bar-track-v"
    assert "top:" in (pill.get("style") or ""), "pill missing top% style"
    assert "bottom:" in (pill.get("style") or ""), "pill missing bottom% style"


def test_stats_contain_rain_probability(rendered_html, tomorrow_forecast):
    soup = BeautifulSoup(rendered_html, "html.parser")
    stats_div = soup.find(id="day-stats")
    all_stat_spans = stats_div.find_all(class_=["stat-primary", "stat-secondary"])
    values = [el.get_text() for el in all_stat_spans]
    rain_prob = str(tomorrow_forecast["rain_probability"])
    assert any(rain_prob in v for v in values), (
        f"Expected a stat span containing '{rain_prob}'; got: {values}"
    )


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


def test_alerts_rendered_for_high_rain(rendered_html):
    """Build a forecast with high rain probability and verify alert is shown."""
    fc = _get_tomorrow_forecast()
    fc["rain_probability"] = 80
    fc["uv_index"] = 2       # below alert threshold
    fc["wind"]["value"] = 10  # well below threshold
    fc["wind"]["unit"] = "kmh"

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")
    alerts_div = soup.find(id="day-alerts")
    assert alerts_div is not None
    alert_texts = [el.get_text() for el in alerts_div.find_all(class_="alert-text")]
    assert any("rain" in t.lower() for t in alert_texts), f"alerts: {alert_texts}"


def test_alerts_rendered_for_high_uv(rendered_html):
    fc = _get_tomorrow_forecast()
    fc["uv_index"] = 9        # Very High
    fc["rain_probability"] = 5
    fc["wind"]["value"] = 10
    fc["wind"]["unit"] = "kmh"

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")
    alerts_div = soup.find(id="day-alerts")
    assert alerts_div is not None
    alert_texts = [el.get_text() for el in alerts_div.find_all(class_="alert-text")]
    assert any("uv" in t.lower() for t in alert_texts), f"alerts: {alert_texts}"


def test_no_alerts_when_nothing_exceeds_threshold():
    fc = _get_tomorrow_forecast()
    fc["rain_probability"] = 20
    fc["uv_index"] = 3
    fc["wind"]["value"] = 20
    fc["wind"]["unit"] = "kmh"

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find(id="day-alerts") is None


def test_hours_of_rain_secondary_shown_when_nonzero():
    fc = _get_tomorrow_forecast()
    fc["hours_of_rain"] = 2.5

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    soup = BeautifulSoup(str(page.airium), "html.parser")
    rain_row = soup.find(class_="stat-rain")
    assert rain_row is not None
    primary = rain_row.find(class_="stat-primary")
    assert primary is not None
    assert "rain" in primary.get_text().lower()
    assert "2.5" in primary.get_text()
    secondary = rain_row.find(class_="stat-secondary")
    assert secondary is not None
    assert str(fc["rain_probability"]) in secondary.get_text()


def test_hours_of_rain_secondary_hidden_when_zero():
    fc = _get_tomorrow_forecast()
    fc["hours_of_rain"] = 0.0

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    soup = BeautifulSoup(str(page.airium), "html.parser")
    rain_row = soup.find(class_="stat-rain")
    assert rain_row is not None
    assert rain_row.find(class_="stat-secondary") is None


def test_uv_secondary_shows_hours_of_sun_when_available():
    fc = _get_tomorrow_forecast()
    fc["uv_index"] = 4
    fc["hours_of_sun"] = 6.0

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    soup = BeautifulSoup(str(page.airium), "html.parser")
    uv_row = soup.find(class_="stat-uv")
    assert uv_row is not None
    primary = uv_row.find(class_="stat-primary")
    assert primary is not None
    assert "sunshine" in primary.get_text().lower()
    assert "6" in primary.get_text()
    secondary = uv_row.find(class_="stat-secondary")
    assert secondary is not None
    assert "uv index" in secondary.get_text().lower()


def test_uv_secondary_falls_back_to_category_when_no_sun_hours():
    fc = _get_tomorrow_forecast()
    fc["uv_index"] = 4
    fc["hours_of_sun"] = None

    page = TomorrowPage(WIDTH, HEIGHT)
    page.template(
        map_url="https://example.test/staticmap",
        tomorrow_forecast=fc,
    )
    soup = BeautifulSoup(str(page.airium), "html.parser")
    uv_row = soup.find(class_="stat-uv")
    assert uv_row is not None
    secondary = uv_row.find(class_="stat-secondary")
    assert secondary is not None
    assert secondary.get_text() == "Moderate"
