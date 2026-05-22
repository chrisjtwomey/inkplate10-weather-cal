from airium import Airium
from .page import Page


class SimplifiedPage(Page):
    def __init__(self, width, height):
        super().__init__("simplified", width, height)

    def _css_links(self, a):
        a.link(rel="stylesheet", href="styles.css")
        a.link(rel="stylesheet", href="simplified.css")

    def _script_tags(self, a):
        pass  # subclasses may add extra <script> tags in <head>

    def template(self, **kwargs):
        self.airium = Airium()
        a = self.airium

        map_url = kwargs["map_url"]
        forecast = kwargs["forecast"]

        forecast_dt = forecast["dt"]
        temp_unit = forecast["temperature"]["unit"]
        temp_min = forecast["temperature"].get("min")
        temp_max = forecast["temperature"]["max"]
        feels_like = forecast["temperature"].get("feels_like")
        rain_prob = forecast["rain_probability"]
        day_phrase = forecast.get("day_phrase")

        self.log.info("Rendering %s page for %s", self.name, forecast_dt.date())

        try:
            date_str = forecast_dt.strftime("%A, %B %-d")
        except ValueError:
            date_str = forecast_dt.strftime("%A, %B %d").replace(" 0", " ")

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(
                    charset="utf-8",
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                a.title(_t="Day Forecast")
                self._css_links(a)
                self._script_tags(a)

            with a.body():
                # ── Map ──────────────────────────────────────────────────
                with a.div(id="day-map-wrapper"):
                    with a.div(id="map-container"):
                        a.img(src=map_url, id="map")

                # ── Content section ───────────────────────────────────────
                with a.div(id="day-body", klass="bg-container"):

                    # ── Hero: icon → date → temperature → phrase ──
                    with a.div(id="day-hero"):
                        a.img(src=forecast["icon"], id="day-icon")
                        a.p(id="day-date", _t=date_str)
                        with a.p(id="day-temp-main"):
                            if temp_min is not None:
                                a.span(id="day-temp-lo", _t=f"{temp_min}°")
                            a.span(id="day-temp-hi", _t=f"{temp_max}{temp_unit}")
                        if feels_like is not None:
                            a.p(id="day-feels-like", _t=f"Feels like {feels_like}\u00b0")
                        if day_phrase:
                            a.p(id="day-phrase", _t=day_phrase)
                        with a.p(id="day-rain-prob"):
                            a.img(src="icon/raindrops.png", klass="day-rain-prob-icon")
                            a.span(_t=f"{rain_prob}% rain")



