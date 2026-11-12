"""The real views, driven end to end through epd_server's regenerate().

Uses the mock weather service (no network) and a fake renderer (no Chromium),
so this proves the wiring — Page.requires <-> WeatherService.datasets() —
rather than pixels.
"""
import datetime as dt

import pytest
from PIL import Image

from weather.mock import mock as _mock_service  # noqa: F401  (registers "mock")
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
    provided = set(weather.datasets()) | {"map_url", "photo_url"}
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
    assert picked is not None
    assert picked["marker"] == "tomorrow"
    assert TomorrowPage.pick_tomorrow(forecasts[:1], today=today) is None


def test_tomorrow_page_skips_when_tomorrow_is_missing(tmp_path, pages):
    tomorrow = pages[-1]
    stale = [{"dt": dt.datetime(2000, 1, 1, 12), "icon": "", "temperature": {"unit": "°C", "max": 1},
              "rain_probability": 0}]
    source = StaticSource(map_url=MAP_URL, daily_forecasts=stale)
    assert regenerate([tomorrow], source) == []
    assert not (tmp_path / "tomorrow.png").exists()


@pytest.mark.parametrize("dataset, skipped", [("hourly_forecasts", "hourly.png"), ("daily_forecasts", "daily.png")])
def test_a_page_with_no_forecasts_is_skipped_and_the_others_render(weather, pages, dataset, skipped):
    data = {**{name: fetch() for name, fetch in weather.datasets().items()}, "map_url": MAP_URL, dataset: []}
    rendered = {p.png_filename for p in regenerate(pages, StaticSource(**data))}
    expected = {p.png_filename for p in pages} - {skipped}
    if dataset == "daily_forecasts":
        expected -= {"tomorrow.png"}
    assert rendered == expected


def test_a_daily_forecast_with_only_past_days_is_skipped(weather, pages):
    data = {**{name: fetch() for name, fetch in weather.datasets().items()}, "map_url": MAP_URL}
    long_ago = dt.datetime(2000, 1, 1)
    data["daily_forecasts"] = [{**f, "dt": long_ago} for f in data["daily_forecasts"]]
    rendered = {p.png_filename for p in regenerate(pages, StaticSource(**data))}
    assert "daily.png" not in rendered and "today.png" in rendered


PHOTO_URL = "file:///data/photos/pictures/abc-123.png"


@pytest.mark.parametrize("cls", [TodayPage, CurrentPage, HourlyPage, DailyPage, TomorrowPage])
def test_a_page_set_to_photos_asks_for_todays_photo_and_shows_it(cls, weather):
    on_map, on_photos = cls(WIDTH, HEIGHT), cls(WIDTH, HEIGHT, picture="photos")
    assert "photo_url" not in on_map.requires and "photo_url" in on_photos.requires
    data = {name: fetch() for name, fetch in weather.datasets().items()}
    tomorrow = dt.date.today() + dt.timedelta(days=1)
    data["daily_forecasts"] = [{**f, "dt": dt.datetime.combine(tomorrow, dt.time())} for f in data["daily_forecasts"]]
    on_photos.template(**{k: v for k, v in {**data, "map_url": MAP_URL, "photo_url": PHOTO_URL}.items()
                          if k in on_photos.requires})
    assert f'src="{PHOTO_URL}"' in str(on_photos.airium) and MAP_URL not in str(on_photos.airium)


def test_a_page_set_to_photos_shows_the_map_when_there_is_no_photo():
    page = TodayPage(WIDTH, HEIGHT, picture="photos")
    assert page.picture_url({"map_url": MAP_URL, "photo_url": ""}) == MAP_URL
    assert page.picture_url({"map_url": MAP_URL, "photo_url": PHOTO_URL}) == PHOTO_URL
    assert TodayPage(WIDTH, HEIGHT).picture_url({"map_url": MAP_URL, "photo_url": PHOTO_URL}) == MAP_URL


def test_regenerate_renders_photo_pages_from_the_photo_source(tmp_path, weather, pages):
    pages[0] = TodayPage(WIDTH, HEIGHT, picture="photos")
    pages[0].html_dir, pages[0].png_dir, pages[0].renderer = pages[1].html_dir, pages[1].png_dir, pages[1].renderer
    source = CompositeSource(StaticSource(map_url=MAP_URL, photo_url=PHOTO_URL), weather)
    assert "today" in [p.name for p in regenerate(pages, source)]
    assert PHOTO_URL in (tmp_path / "html" / "today.html").read_text()
