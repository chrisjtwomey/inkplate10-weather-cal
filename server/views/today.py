import datetime as dt
from .simplified import SimplifiedPage


class TodayPage(SimplifiedPage):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.name = "today"

    def template(self, **kwargs):
        cc = kwargs["current_conditions"]
        super().template(
            map_url=kwargs["map_url"],
            forecast={
                "dt": dt.datetime.now(),
                "icon": cc["icon"],
                "temperature": {
                    "unit": cc["temperature"]["unit"],
                    "min": None,  # current conditions has no daily min
                    "max": cc["temperature"]["value"],
                },
                "wind": cc["wind"],
                "rain_probability": 0,  # not available from current conditions
                "uv_index": cc.get("uv_index"),
                "day_phrase": cc.get("weather_text"),
            },
        )
