"""validate_config(): this project's keys on top of epd_server's core blocks.

Exits (SystemExit) on any problem so a bad config.yaml fails fast at startup.
"""
import pytest

from server import validate_config


def base():
    return {
        "server": {"port": 8080, "timezone": "Europe/Dublin"},
        "display": {"pools": {"today": ["today.png"], "hourly": ["hourly.png"]},
                    "schedule": {"type": "times", "09:00:00": "today", "18:00:00": "hourly"}},
        "weather": {"service": "mock", "num_hourly_forecasts": 9, "metric": True},
        "google": {"apikey": "G", "staticmaps_mapid": "M"},
        "location": "  Dublin ",
        "image": {"width": 825, "height": 1200},
        "mqtt": {"enabled": False},
    }


def test_happy_path_flattens_core_and_project_keys():
    cfg = validate_config(base())
    assert cfg.core.server.port == 8080
    assert str(cfg.core.server.timezone) == "Europe/Dublin"
    assert list(cfg.core.server.schedule) == [("09:00:00", "today"), ("18:00:00", "hourly")]
    assert cfg.core.server.schedule.pages() == {"today.png", "hourly.png"}
    assert cfg.core.server.regen_lead_seconds == 120                       # core default
    assert (cfg.core.image.width, cfg.core.image.inner_width) == (825, 825)
    assert cfg.weather_service == "mock" and cfg.weather_apikey is None
    assert cfg.num_hourly_forecasts == 9
    assert cfg.location == "Dublin"                            # stripped
    assert cfg.core.mqtt.prefix == "mqtt/weather-cal"               # project default
    assert cfg.logs_path == "data/board-logs.db"
    assert cfg.logs_days == 90
    assert cfg.core.server.debug is False


def test_mock_service_needs_no_apikey_but_others_do(caplog):
    c = base()
    c["weather"] = {"service": "accuweather"}
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "weather.apikey not in config but is required" in caplog.text


@pytest.mark.parametrize("service", ["meteireann", "openmeteo", "mock"])
def test_a_provider_with_an_open_api_needs_no_apikey(service):
    c = base()
    c["weather"] = {"service": service}
    assert validate_config(c).weather_apikey is None


def test_unknown_weather_service_exits_with_choices(caplog):
    c = base()
    c["weather"]["service"] = "nope"
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "weather.service 'nope' is not supported" in caplog.text
    assert "mock" in caplog.text


def test_missing_google_key_exits_cleanly(caplog):
    c = base()
    del c["google"]["apikey"]
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "google.apikey not in config but is required" in caplog.text


def test_the_map_is_from_google_when_no_provider_is_set():
    cfg = validate_config(base())
    assert (cfg.map_provider, cfg.google_apikey, cfg.staticmaps_mapid) == ("google", "G", "M")
    assert cfg.geoapify_apikey is None


def test_geoapify_needs_its_key_and_not_googles(caplog):
    c = base()
    c["map"] = {"provider": "geoapify"}
    del c["google"]
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "geoapify.apikey not in config but is required" in caplog.text

    c["geoapify"] = {"apikey": "GEO"}
    cfg = validate_config(c)
    assert (cfg.map_provider, cfg.geoapify_apikey, cfg.google_apikey) == ("geoapify", "GEO", None)


def test_openfreemap_needs_no_key():
    c = base()
    c["map"] = {"provider": "openfreemap"}
    del c["google"]
    assert validate_config(c).map_provider == "openfreemap"


def test_an_unknown_map_provider_exits_with_choices(caplog):
    c = base()
    c["map"] = {"provider": "bing"}
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "map.provider 'bing' is not supported (choose from: google, geoapify, openfreemap)" in caplog.text


def test_core_block_errors_also_exit(caplog):
    c = base()
    c["server"]["timezone"] = "Mars/Olympus"
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "not a valid IANA zone" in caplog.text


def test_negative_hourly_forecasts_rejected(caplog):
    c = base()
    c["weather"]["num_hourly_forecasts"] = -1
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "num_hourly_forecasts must be non-negative" in caplog.text


def test_board_logs_can_be_kept_elsewhere_and_for_longer():
    c = base()
    c["logs"] = {"path": "/var/lib/weather-cal/logs.db", "keep_days": 365}
    cfg = validate_config(c)
    assert (cfg.logs_path, cfg.logs_days) == ("/var/lib/weather-cal/logs.db", 365)


def test_a_bad_logs_keep_days_is_refused(caplog):
    c = base()
    c["logs"] = {"keep_days": "a week"}
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "logs.keep_days" in caplog.text


@pytest.mark.parametrize("value", ["six", True, 2.5, -1])
def test_a_bad_hourly_count_is_a_clear_error(value, caplog):
    c = base()
    c["weather"]["num_hourly_forecasts"] = value
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "weather.num_hourly_forecasts must be non-negative" in caplog.text


@pytest.mark.parametrize("value", [123, 1.5, ["Cork"]])
def test_a_location_that_is_not_text_is_a_clear_error(value, caplog):
    c = base()
    c["location"] = value
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "location must be a place name" in caplog.text


def test_every_page_shows_the_map_unless_set():
    cfg = validate_config(base())
    assert cfg.pictures == {"today": "map", "current": "map", "hourly": "map", "daily": "map", "tomorrow": "map"}


def test_a_page_can_show_photos():
    c = base()
    c["picture"] = {"hourly": "photos"}
    assert validate_config(c).pictures["hourly"] == "photos"


@pytest.mark.parametrize("picture, words", [
    ({"weekly": "photos"}, "picture.weekly: no such page (choose from: today, current, hourly, daily, tomorrow)"),
    ({"today": "photo"}, "picture.today must be map or photos (got 'photo')"),
    (["today"], "picture must name pages, such as today: photos"),
])
def test_a_bad_picture_setting_is_a_clear_error(picture, words, caplog):
    c = base()
    c["picture"] = picture
    with pytest.raises(SystemExit):
        validate_config(c)
    assert words in caplog.text


def test_every_page_uses_the_classic_theme_unless_set():
    assert set(validate_config(base()).page_themes.values()) == {"classic"}
    c = base()
    c["pages"] = {"hourly": {"theme": "classic"}}
    assert validate_config(c).page_themes["hourly"] == "classic"


@pytest.mark.parametrize("pages, words", [
    ({"today": {"theme": "neon"}}, "pages.today.theme 'neon' does not exist (choose from: classic)"),
    ({"weekly": {"theme": "classic"}}, "pages.weekly: no such page (choose from: today, current, hourly, daily, tomorrow)"),
    ({"today": "classic"}, "pages.today must hold settings, such as theme: classic"),
    (["today"], "pages must name page types"),
])
def test_a_bad_page_theme_is_a_clear_error(pages, words, caplog):
    c = base()
    c["pages"] = pages
    with pytest.raises(SystemExit):
        validate_config(c)
    assert words in caplog.text


def test_a_theme_without_that_page_type_is_a_clear_error(monkeypatch, caplog):
    import server
    from views.themes import THEMES, Theme
    monkeypatch.setitem(THEMES, "tiny", Theme("tiny", "Tiny", {"today": THEMES["classic"].pages["today"]}))
    c = base()
    c["pages"] = {"today": {"theme": "tiny"}}
    assert validate_config(c).page_themes["today"] == "tiny"
    c["pages"] = {"hourly": {"theme": "tiny"}}
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "pages.hourly.theme 'tiny' has no hourly page" in caplog.text
    assert server.THEMES is THEMES


def test_a_pages_photos_and_map_kind():
    cfg = validate_config(base())
    assert set(cfg.page_photos.values()) == {None} and set(cfg.page_maps.values()) == {"classic"}
    c = base()
    c["pages"] = {"today": {"photos": ["abc", "def"], "map": "classic"}}
    cfg = validate_config(c)
    assert cfg.page_photos["today"] == ["abc", "def"] and cfg.page_photos["hourly"] is None


@pytest.mark.parametrize("block, words", [
    ({"photos": "abc"}, "pages.today.photos must be a list of photo ids"),
    ({"photos": [1, 2]}, "pages.today.photos must be a list of photo ids"),
    ({"map": "relief"}, "pages.today.map 'relief' does not exist (choose from: classic)"),
])
def test_a_bad_pages_photos_or_map_is_a_clear_error(block, words, caplog):
    c = base()
    c["pages"] = {"today": block}
    with pytest.raises(SystemExit):
        validate_config(c)
    assert words in caplog.text


def test_a_picture_size_belongs_to_a_theme_and_a_page():
    assert validate_config(base()).picture_sizes == {}
    c = base()
    c["themes"] = {"classic": {"today": {"picture_size": 55}, "hourly": {}}}
    assert validate_config(c).picture_sizes == {"classic": {"today": 55}}


@pytest.mark.parametrize("themes, words", [
    ({"neon": {"today": {"picture_size": 50}}}, "themes.neon: no such theme (choose from: classic)"),
    ({"classic": {"weekly": {"picture_size": 50}}}, "themes.classic.weekly: the theme has no such page"),
    ({"classic": {"today": 50}}, "themes.classic.today must hold settings, such as picture_size: 50"),
    ({"classic": {"today": {"picture_size": 0}}}, "themes.classic.today.picture_size must be a percent"),
    ({"classic": {"today": {"picture_size": True}}}, "themes.classic.today.picture_size must be a percent"),
    ({"classic": ["today"]}, "themes.classic must name pages"),
    (["classic"], "themes must name themes"),
])
def test_a_bad_picture_size_is_a_clear_error(themes, words, caplog):
    c = base()
    c["themes"] = themes
    with pytest.raises(SystemExit):
        validate_config(c)
    assert words in caplog.text
