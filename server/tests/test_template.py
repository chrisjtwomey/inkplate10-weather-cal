"""
HTML structure check for `CalendarPage.template()`.

We feed mock weather data into the template, then serialize the underlying
`airium` document and assert its structure with BeautifulSoup. Selenium /
Chromium rendering is *not* invoked here — that's covered by the end-to-end
docker run separately. The goal is to catch airium / Pillow / template-call
regressions when bumping deps, without needing a browser.
"""
from datetime import datetime

import pytest
from bs4 import BeautifulSoup
from freezegun import freeze_time

from views.calendar import CalendarPage
from weather.mock.mock import MockWeatherService


NUM_HOURS = 6
WIDTH = 825
HEIGHT = 1200


@pytest.fixture
def rendered_html():
    """Render the calendar template at a fixed wall-clock and return the HTML."""
    with freeze_time("2026-05-19 09:00:00"):
        page = CalendarPage(WIDTH, HEIGHT)
        weather = MockWeatherService(num_hours=NUM_HOURS, metric=True)
        page.template(
            map_url="https://example.test/staticmap?center=51.9,-8.5",
            daily_summary=weather.get_daily_summary(),
            hourly_forecasts=weather.get_hourly_forecast(),
        )
        return str(page.airium)


def test_html_is_well_formed(rendered_html):
    assert rendered_html.startswith("<!DOCTYPE html>")
    soup = BeautifulSoup(rendered_html, "html.parser")
    assert soup.html is not None
    assert soup.head is not None
    assert soup.body is not None


def test_top_banner_has_date_month_temp_icon(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    banner = soup.find(id="top-banner")
    assert banner is not None

    assert banner.find(id="date").get_text(strip=True) == "19"             # frozen day
    assert banner.find(id="month").get_text(strip=True) == "May"

    temp_el = banner.find(id="temp")
    assert temp_el is not None
    assert "°C" in temp_el.get_text() or "C" in temp_el.get_text()

    icon_container = banner.find(id="icon-container")
    assert icon_container is not None
    assert icon_container.find("img") is not None, "expected a weather icon img tag"


def test_map_image_uses_provided_url(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    img = soup.find(id="map")
    assert img is not None
    assert img["src"] == "https://example.test/staticmap?center=51.9,-8.5"


def test_forecast_table_has_one_cell_per_hour_per_row(rendered_html):
    """
    Template emits 4 rows: icon, hour label, temperature, precip canvas.
    Each row has NUM_HOURS cells.
    """
    soup = BeautifulSoup(rendered_html, "html.parser")
    table = soup.find(id="forecast-table")
    assert table is not None

    rows = table.find_all("tr")
    assert len(rows) == 4, f"expected 4 rows (icon/hour/temp/precip); got {len(rows)}"
    for row in rows:
        cells = row.find_all("td")
        assert len(cells) == NUM_HOURS

    # Each cell in row 0 (icons) holds an <img>.
    for cell in rows[0].find_all("td"):
        assert cell.find("img") is not None

    # Each cell in row 3 (precip) holds a <canvas> with a data_precip attribute
    # that's a parseable integer percentage.
    for cell in rows[3].find_all("td"):
        canvas = cell.find("canvas")
        assert canvas is not None
        pct = int(canvas["data_precip"])
        assert 0 <= pct <= 100


def test_external_chart_libraries_are_loaded(rendered_html):
    """Roughjs + Chart.js are required by the precipitation canvas script."""
    soup = BeautifulSoup(rendered_html, "html.parser")
    srcs = {s.get("src") for s in soup.find_all("script") if s.get("src")}
    assert any("rough" in s for s in srcs), "expected roughjs to be loaded"
    assert any("chart.js" in s for s in srcs), "expected chart.js to be loaded"


def test_local_stylesheet_link_present(rendered_html):
    soup = BeautifulSoup(rendered_html, "html.parser")
    link = soup.find("link", rel="stylesheet")
    assert link is not None
    assert link["href"] == "styles.css"


def test_repeated_template_calls_do_not_stack_content():
    """
    Regression for the overnight-accumulation bug: calling template() twice on
    the same CalendarPage used to append a second full page worth of HTML to
    the airium buffer, producing a double-date PNG. The fix resets self.airium
    at the top of template(); this test locks that in.
    """
    weather = MockWeatherService(num_hours=NUM_HOURS, metric=True)
    kwargs = dict(
        map_url="https://example.test/map",
        daily_summary=weather.get_daily_summary(),
        hourly_forecasts=weather.get_hourly_forecast(),
    )

    page = CalendarPage(WIDTH, HEIGHT)
    with freeze_time("2026-05-16 09:00:00"):
        page.template(**kwargs)
        page.template(**kwargs)  # second call simulates scheduled regen

    html = str(page.airium)
    soup = BeautifulSoup(html, "html.parser")

    date_elements = soup.find_all(id="date")
    assert len(date_elements) == 1, (
        f"expected exactly 1 #date element after two template() calls, got {len(date_elements)}"
    )

    top_banners = soup.find_all(id="top-banner")
    assert len(top_banners) == 1, (
        f"expected exactly 1 #top-banner after two template() calls, got {len(top_banners)}"
    )
