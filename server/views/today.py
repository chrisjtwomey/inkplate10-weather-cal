import datetime as dt
from .simplified import SimplifiedPage


class TodayPage(SimplifiedPage):
    requires = ("map_url", "daily_summary")

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
        self.name = "today"

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="tomorrow.css")

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
                    "max": temp.get("max", temp.get("value")),
                    "feels_like": temp.get("feels_like"),
                },
                "wind": ds.get("wind"),
                "rain_probability": ds.get("rain_probability", 0),
                "uv_index": ds.get("uv_index"),
                "day_phrase": ds.get("day_phrase"),
                "pollen": ds.get("pollen"),
            },
        )
