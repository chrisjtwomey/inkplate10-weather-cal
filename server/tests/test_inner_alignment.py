import pytest

from server import validate_config
from views.page import Page


def _base_config():
    return {
        "server": {
            "port": 8080,
            "timezone": "Europe/Dublin",
            "regen_lead_seconds": 120,
        },
        "display_schedule": {"09:00:00": "today.png"},
        "weather": {
            "service": "mock",
            "apikey": "XXXX",
            "num_hourly_forecasts": 9,
            "metric": True,
        },
        "google": {
            "apikey": "XXXX",
            "staticmaps_mapid": "XXXX",
        },
        "location": "Dublin",
        "image": {
            "width": 825,
            "height": 1200,
            "innerWidth": 650,
            "innerHeight": 900,
        },
        "mqtt": {
            "enabled": False,
            "host": "localhost",
            "port": 1883,
            "topic": "mqtt/eink-cal-client",
        },
    }


def test_alignment_defaults_to_center_center():
    cfg = validate_config(_base_config())
    assert cfg.image_inner_align_x == "center"
    assert cfg.image_inner_align_y == "center"


def test_accepts_alignment_options():
    config = _base_config()
    config["image"]["innerAlignX"] = "left"
    config["image"]["innerAlignY"] = "bottom"

    cfg = validate_config(config)
    assert cfg.image_inner_align_x == "left"
    assert cfg.image_inner_align_y == "bottom"


@pytest.mark.parametrize(
    "key,value",
    [
        ("innerAlignX", "middle"),
        ("innerAlignX", "top"),
        ("innerAlignY", "left"),
        ("innerAlignY", "middle"),
    ],
)
def test_rejects_invalid_alignment_values(key, value):
    config = _base_config()
    config["image"][key] = value

    with pytest.raises(SystemExit):
        validate_config(config)


def test_layout_css_variables_reflect_left_bottom_alignment():
    page = Page(
        "dummy",
        825,
        1200,
        inner_width=650,
        inner_height=900,
        inner_align_x="left",
        inner_align_y="bottom",
    )
    style = page.layout_css_variables()

    assert "--inner-pad-left:0px;" in style
    assert "--inner-pad-right:175px;" in style
    assert "--inner-pad-top:300px;" in style
    assert "--inner-pad-bottom:0px;" in style
