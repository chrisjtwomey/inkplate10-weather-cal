import datetime as dt
from .simplified import SimplifiedPage


class CurrentPage(SimplifiedPage):
    def __init__(
        self,
        width,
        height,
        inner_width=None,
        inner_height=None,
        inner_align_x="center",
        inner_align_y="center",
    ):
        super().__init__(
            width,
            height,
            inner_width,
            inner_height,
            inner_align_x,
            inner_align_y,
        )
        self.name = "current"

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="current.css")

    def template(self, **kwargs):
        cc = kwargs["current_conditions"]
        daily_summary = kwargs.get("daily_summary")

        super().template(
            map_url=kwargs["map_url"],
            forecast={
                "dt": dt.datetime.now(),
                "icon": cc["icon"],
                "temperature": {
                    "unit": cc["temperature"]["unit"],
                    "min": daily_summary["temperature"].get("min") if daily_summary else None,
                    "max": cc["temperature"]["value"],
                    "feels_like": cc["temperature"].get("feels_like"),
                },
                "wind": cc["wind"],
                "rain_probability": daily_summary.get("rain_probability", 0) if daily_summary else 0,
                "uv_index": cc.get("uv_index"),
                "day_phrase": cc.get("weather_text"),
                "pollen": daily_summary.get("pollen") if daily_summary else None,
            },
        )
