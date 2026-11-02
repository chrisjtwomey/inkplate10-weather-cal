import datetime as dt
from .simplified import SimplifiedPage


class TodayPage(SimplifiedPage):
    requires = ("map_url", "daily_summary")

    def __init__(self, *geometry, **kwargs):
        super().__init__(*geometry, **kwargs)
        self.name = "today"

    def template(self, **kwargs):
        ds = kwargs["daily_summary"]
        temp = ds["temperature"]

        super().template(
            map_url=kwargs["map_url"],
            forecast={
                "dt": dt.datetime.now(),
                "icon": ds["icon"],
                "temperature": {
                    "unit": temp["unit"],
                    "min": temp.get("min"),
                    "max": temp["max"],
                    "feels_like": temp.get("feels_like"),
                },
                "wind": ds.get("wind"),
                "rain_probability": ds.get("rain_probability", 0),
                "uv_index": ds.get("uv_index"),
                "day_phrase": ds.get("day_phrase"),
                "pollen": ds.get("pollen"),
            },
        )
