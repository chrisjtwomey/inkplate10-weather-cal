"""The real views, driven end to end through epd_server's regenerate().

Uses the mock weather service (no network) and a fake renderer (no Chromium),
so this proves the wiring — Page.requires <-> WeatherService.datasets() —
rather than pixels.
"""
import datetime as dt

import pytest
from PIL import Image

import weather.mock.mock  # noqa: F401  (registers "mock")
from epd_server.pipeline import regenerate
from epd_server.source import CompositeSource, StaticSource
from views.current import CurrentPage
from views.daily import DailyPage
from views.hourly import HourlyPage
from views.today import TodayPage
from views.tomorrow import TomorrowPage
from weather.registry import create
from weather.service import WeatherService

WIDTH, HEIGHT = 825, 1200
MAP_URL = "map-cache/staticmap_test.png"


class FakeRenderer:
    def __init__(self):
        self.rendered = []

    def render(self, html_path, width, height):
        self.rendered.append(html_path)
        return Image.new("RGB", (width, height), (200, 200, 200))


@pytest.fixture
def weather():
    return create("mock", location="Dublin", num_hours=9, metric=True)


@pytest.fixture
def pages(tmp_path):
    renderer = FakeRenderer()
    ps = [
        TodayPage(WIDTH, HEIGHT),
        CurrentPage(WIDTH, HEIGHT),
        HourlyPage(WIDTH, HEIGHT),
        DailyPage(WIDTH, HEIGHT),
        TomorrowPage(WIDTH, HEIGHT),
    ]
    for p in ps:
        p.html_dir = str(tmp_path / "html")
        p.png_dir = str(tmp_path)
        p.renderer = renderer
    return ps


def test_mock_service_is_a_datasource(weather):
    assert isinstance(weather, WeatherService)
    assert set(weather.datasets()) == {
        "current_conditions", "daily_summary", "hourly_forecasts", "daily_forecasts",
    }


def test_every_view_requires_only_what_the_source_provides(weather):
    provided = set(weather.datasets()) | {"map_url"}
    for cls in (TodayPage, CurrentPage, HourlyPage, DailyPage, TomorrowPage):
        assert cls.requires, f"{cls.__name__} declares no requires"
        missing = set(cls.requires) - provided
        assert not missing, f"{cls.__name__} requires {missing} which nothing provides"


def test_regenerate_all_renders_every_page(tmp_path, weather, pages):
    source = CompositeSource(StaticSource(map_url=MAP_URL), weather)
    rendered = regenerate(pages, source)
    names = [p.name for p in rendered]
    # tomorrow may legitimately skip if the mock's 5-day forecast lacks tomorrow
    assert names[:4] == ["today", "current", "hourly", "daily"]
    for name in names:
        assert (tmp_path / f"{name}.png").exists()
        assert (tmp_path / "html" / f"{name}.html").exists()
        assert Image.open(tmp_path / f"{name}.png").mode == "L"


def test_regenerate_one_page_by_filename_touches_only_that_page(tmp_path, weather, pages):
    source = CompositeSource(StaticSource(map_url=MAP_URL), weather)
    rendered = regenerate(pages, source, only="hourly.png")
    assert [p.name for p in rendered] == ["hourly"]
    assert (tmp_path / "hourly.png").exists()
    assert not (tmp_path / "today.png").exists()
    assert pages[0].renderer.rendered == [str(tmp_path / "html" / "hourly.html")]


def test_tomorrow_page_picks_tomorrow_from_daily_forecasts():
    today = dt.date(2026, 7, 1)
    forecasts = [
        {"dt": dt.datetime(2026, 7, 1, 12)},
        {"dt": dt.datetime(2026, 7, 2, 12), "marker": "tomorrow"},
        {"dt": dt.datetime(2026, 7, 3, 12)},
    ]
    picked = TomorrowPage.pick_tomorrow(forecasts, today=today)
    assert picked["marker"] == "tomorrow"
    assert TomorrowPage.pick_tomorrow(forecasts[:1], today=today) is None


def test_tomorrow_page_skips_when_tomorrow_is_missing(tmp_path, pages):
    tomorrow = pages[-1]
    stale = [{"dt": dt.datetime(2000, 1, 1, 12), "icon": "", "temperature": {"unit": "°C", "max": 1},
              "rain_probability": 0}]
    source = StaticSource(map_url=MAP_URL, daily_forecasts=stale)
    assert regenerate([tomorrow], source) == []
    assert not (tmp_path / "tomorrow.png").exists()
