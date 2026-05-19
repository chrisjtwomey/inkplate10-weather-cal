"""
HTML structure check for `DailyPage.template()`.

We feed mock weather data into the template, then serialize the underlying
`airium` document and assert its structure with BeautifulSoup. Selenium /
Chromium rendering is *not* invoked here — that's covered by the end-to-end
docker run separately.
"""
import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time

from views.daily import DailyPage
from weather.mock.mock import MockWeatherService

WIDTH = 825
HEIGHT = 1200
# Expected columns per row when UV and sun data are present (5 base + UV + sun)
NUM_COLS_FULL = 7
# Base columns when UV and sun data are absent
NUM_COLS_BASE = 5


@pytest.fixture
def mock_forecasts():
    """Five-day forecast from the mock service (always has UV + sun data)."""
    with freeze_time("2026-05-19 09:00:00"):
        weather = MockWeatherService(metric=True)
        return weather.get_5day_forecast()


@pytest.fixture
def rendered_html(mock_forecasts):
    """Render the daily template at a fixed wall-clock and return the HTML."""
    weather = MockWeatherService(metric=True)
    with freeze_time("2026-05-19 09:00:00"):
        page = DailyPage(WIDTH, HEIGHT)
        page.template(
            map_url="https://example.test/staticmap?center=51.9,-8.5",
            daily_summary=weather.get_daily_summary(),
            daily_forecasts=mock_forecasts,
        )
        return str(page.airium)


def test_html_is_well_formed(rendered_html):
    assert rendered_html.startswith("<!DOCTYPE html>")
    soup = BeautifulSoup(rendered_html, "html.parser")
    assert soup.html is not None
    assert soup.head is not None
    assert soup.body is not None


def test_header_shows_frozen_date_and_location(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    banner = soup.find(id="top-banner")
    assert banner is not None

    assert banner.find(id="date").get_text(strip=True) == "19"
    assert banner.find(id="month").get_text(strip=True) == "May"

    # temp and icon come from daily_summary, same as the today page
    assert banner.find(id="temp") is not None
    assert banner.find(id="icon-container") is not None


def test_map_image_uses_provided_url(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    img = soup.find(id="map")
    assert img is not None
    assert img["src"] == "https://example.test/staticmap?center=51.9,-8.5"



    soup = BeautifulSoup(rendered_html, "html.parser")
    table = soup.find(id="daily-table")
    assert table is not None

    rows = table.find_all("tr", class_="day-row")
    assert len(rows) == 5, f"expected 5 day rows, got {len(rows)}"


def test_each_row_has_correct_cell_count(rendered_html):
    """Mock service always provides UV + sun data → 7 cells per row."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    rows = soup.find_all("tr", class_="day-row")
    for row in rows:
        cells = row.find_all("td")
        assert len(cells) == NUM_COLS_FULL, (
            f"expected {NUM_COLS_FULL} cells per row, got {len(cells)}"
        )


def test_temp_bar_pill_positions_are_valid(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    tracks = soup.find_all("div", class_="temp-bar-track")
    assert len(tracks) == 5

    for track in tracks:
        pill = track.find("div", class_="temp-bar-pill")
        assert pill is not None, "temp-bar-track missing temp-bar-pill child"
        style = pill.get("style", "")
        # style should be e.g. "left:10.5%;right:20.3%"
        assert "left:" in style and "right:" in style, (
            f"pill missing left/right positioning: {style!r}"
        )
        left_pct  = float(style.split("left:")[1].split("%")[0])
        right_pct = float(style.split("right:")[1].split("%")[0])
        assert 0.0 <= left_pct  <= 100.0
        assert 0.0 <= right_pct <= 100.0
        assert left_pct + right_pct < 100.0, "pill has no visible width"


def test_precip_cells_show_icon_and_percentage(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    cells = soup.find_all("td", class_="day-precip-cell")
    assert len(cells) == 5

    for cell in cells:
        assert cell.find("img", class_="precip-icon") is not None
        pct_text = cell.find("span", class_="precip-value").get_text(strip=True)
        pct = int(pct_text.rstrip("%"))
        assert 0 <= pct <= 100


def test_each_row_has_weather_icon(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    rows = soup.find_all("tr", class_="day-row")
    for row in rows:
        icon_cell = row.find("td", class_="day-icon-cell")
        assert icon_cell is not None
        assert icon_cell.find("img") is not None


def test_wind_cells_have_arrow_and_speed(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    rows = soup.find_all("tr", class_="day-row")
    for row in rows:
        wind_cell = row.find("td", class_="day-wind-cell")
        assert wind_cell is not None
        assert wind_cell.find("img", class_="wind-arrow") is not None
        assert wind_cell.find("span", class_="wind-speed") is not None


def test_uv_cells_present_with_mock_data(rendered_html):
    """Mock service always has UV data → uv cells should appear with sun icon."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    uv_cells = soup.find_all("td", class_="day-uv-cell")
    assert len(uv_cells) == 5
    for cell in uv_cells:
        assert cell.find("img", class_="uv-icon") is not None
        uv_val = cell.find("span", class_="uv-value")
        assert uv_val is not None
        assert 0 <= int(uv_val.get_text(strip=True)) <= 11


def test_sun_cells_present_with_mock_data(rendered_html):
    """Mock service always has sunrise/sunset → sun cells should appear."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    sun_cells = soup.find_all("td", class_="day-sun-cell")
    assert len(sun_cells) == 5


def test_roughjs_is_not_loaded(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    srcs = {s.get("src") for s in soup.find_all("script") if s.get("src")}
    assert not any("rough" in (s or "") for s in srcs), "roughjs script tag should be removed"


def test_stylesheets_loaded(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    hrefs = [l["href"] for l in soup.find_all("link", rel="stylesheet")]
    assert "styles.css" in hrefs, "expected styles.css to be linked"
    assert "daily.css" in hrefs, "expected daily.css to be linked"


def test_repeated_template_calls_do_not_stack_content(mock_forecasts):
    """
    Calling template() twice must not accumulate two copies of the page HTML.
    """
    weather = MockWeatherService(metric=True)
    page = DailyPage(WIDTH, HEIGHT)
    kwargs = dict(
        map_url="https://example.test/map",
        daily_summary=weather.get_daily_summary(),
        daily_forecasts=mock_forecasts,
    )
    with freeze_time("2026-05-16 09:00:00"):
        page.template(**kwargs)
        page.template(**kwargs)

    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")

    date_elements = soup.find_all(id="date")
    assert len(date_elements) == 1, (
        f"expected 1 #date element after two template() calls, got {len(date_elements)}"
    )
