import datetime as dt
from .simplified import SimplifiedPage


class TodayPage(SimplifiedPage):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.name = "today"

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="tomorrow.css")

    def template(self, **kwargs):
        cc = kwargs["current_conditions"]
        ds = kwargs.get("daily_summary")

        super().template(
            map_url=kwargs["map_url"],
            forecast={
                "dt": dt.datetime.now(),
                "icon": cc["icon"],
                "temperature": {
                    "unit": cc["temperature"]["unit"],
                    "min": ds["temperature"]["min"] if ds else None,
                    "max": cc["temperature"]["value"],
                    "feels_like": cc["temperature"].get("feels_like"),
                },
                "wind": cc["wind"],
                "rain_probability": ds["rain_probability"] if ds else 0,
                "uv_index": cc.get("uv_index"),
                "day_phrase": cc.get("weather_text"),
                "pollen": ds.get("pollen") if ds else None,
            },
        )
