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
    assert cfg.port == 8080
    assert str(cfg.timezone) == "Europe/Dublin"
    assert list(cfg.schedule) == [("09:00:00", "today"), ("18:00:00", "hourly")]
    assert cfg.schedule.pages() == {"today.png", "hourly.png"}
    assert cfg.regen_lead_seconds == 120                       # core default
    assert (cfg.image_width, cfg.image_inner_width) == (825, 825)
    assert cfg.weather_service == "mock" and cfg.weather_apikey is None
    assert cfg.num_hourly_forecasts == 9
    assert cfg.location == "Dublin"                            # stripped
    assert cfg.mqtt_topic == "mqtt/eink-cal-client"            # project default
    assert cfg.debug is False


def test_mock_service_needs_no_apikey_but_others_do(caplog):
    c = base()
    c["weather"] = {"service": "accuweather"}
    with pytest.raises(SystemExit):
        validate_config(c)
    assert "weather.apikey not in config but is required" in caplog.text


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
