import datetime as dt

from epd_server.page import SkipPage

from .simplified import SimplifiedPage


class TomorrowPage(SimplifiedPage):
    requires = ("map_url", "daily_forecasts")

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
        self.name = "tomorrow"

    @staticmethod
    def pick_tomorrow(daily_forecasts, today=None):
        """Return tomorrow's entry from a 5-day forecast, or None."""
        today = today if today is not None else dt.date.today()
        tomorrow = today + dt.timedelta(days=1)
        return next((f for f in daily_forecasts if f["dt"].date() == tomorrow), None)

    def template(self, **kwargs):
        forecast = kwargs.get("tomorrow_forecast")
        if forecast is None:
            forecast = self.pick_tomorrow(kwargs["daily_forecasts"])
        if forecast is None:
            raise SkipPage("no forecast entry for tomorrow in daily_forecasts")
        super().template(map_url=kwargs["map_url"], forecast=forecast)

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="tomorrow.css")
