import datetime as dt
from .simplified import SimplifiedPage


class CurrentPage(SimplifiedPage):
    requires = ("map_url", "current_conditions", "daily_summary")

    def __init__(self, *geometry, **kwargs):
        super().__init__(*geometry, **kwargs)
        self.name = "current"

    def _rounded_hour_phrase(self, now: dt.datetime) -> str:
        return self.words.hour((now + dt.timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0))

    def template(self, **kwargs):
        now = dt.datetime.now()
        cc = kwargs["current_conditions"]
        daily_summary = kwargs.get("daily_summary")

        super().template(
            map_url=self.picture_url(kwargs),
            forecast={
                "dt": now,
                "date_phrase": self._rounded_hour_phrase(now),
                "icon": cc["icon"],
                "temperature": {
                    "unit": cc["temperature"]["unit"],
                    "min": None,
                    "max": cc["temperature"]["value"],
                },
                "rain_probability": daily_summary.get("rain_probability", 0) if daily_summary else 0,
                "day_phrase": cc.get("weather_text"),
            },
        )
