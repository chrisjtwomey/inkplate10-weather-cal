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

    @staticmethod
    def _rounded_hour_phrase(now: dt.datetime) -> str:
        rounded = (now + dt.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0)
        hour_24 = rounded.hour
        hour_12 = hour_24 % 12 or 12
        suffix = "am" if hour_24 < 12 else "pm"
        return f"{hour_12}{suffix}"

    def template(self, **kwargs):
        now = dt.datetime.now()
        cc = kwargs["current_conditions"]
        daily_summary = kwargs.get("daily_summary")

        super().template(
            map_url=kwargs["map_url"],
            forecast={
                "dt": now,
                "date_phrase": self._rounded_hour_phrase(now),
                "icon": cc["icon"],
                "temperature": {
                    "unit": cc["temperature"]["unit"],
                    "min": None,
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
