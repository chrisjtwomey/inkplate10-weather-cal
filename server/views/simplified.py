from airium import Airium
from .page import Page


class SimplifiedPage(Page):
    def __init__(self, *geometry, **kwargs):
        super().__init__("simplified", *geometry, **kwargs)

    def template(self, **kwargs):
        self.airium = Airium()
        a = self.airium

        map_url = kwargs["map_url"]
        forecast = kwargs["forecast"]

        forecast_dt = forecast["dt"]
        temp_unit = forecast["temperature"]["unit"]
        temp_min = forecast["temperature"].get("min")
        temp_max = forecast["temperature"]["max"]
        rain_prob = forecast["rain_probability"]
        day_phrase = forecast.get("day_phrase")
        date_phrase = forecast.get("date_phrase")

        self.log.info("Rendering %s page for %s", self.name, forecast_dt.date())

        if date_phrase is None:
            date_phrase = self.words.date_long(forecast_dt)

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(charset="utf-8")
                a.meta(name="viewport", content="width=device-width, initial-scale=1")
                a.title(_t=self.words["title_today"])
                a.link(rel="stylesheet", href="styles.css")
                a.link(rel="stylesheet", href="simplified.css")

            with a.body(style=self.layout_css_variables()):
                with a.div(klass="inner-canvas-outer"):
                    with a.div(klass="inner-canvas"):
                        with a.div(klass="inner-canvas-content"):
                            # ── Map ──────────────────────────────────────────────────
                            with a.div(id="day-map-wrapper"):
                                a.img(src=forecast["icon"], id="day-icon-bg")
                                with a.div(id="map-container", **{"data-picture": "main"}):
                                    a.img(src=map_url, id="map")

                            # ── Content section ───────────────────────────────────────
                            with a.div(id="day-body", klass="bg-container"):

                                # ── Hero: icon → date → temperature → phrase ──
                                with a.div(id="day-hero"):
                                    a.img(src=forecast["icon"], id="day-icon")
                                    a.p(id="day-date", _t=date_phrase)
                                    with a.p(id="day-temp-main"):
                                        if temp_min is not None:
                                            a.span(id="day-temp-lo", _t=f"{temp_min}°")
                                        a.span(id="day-temp-hi", _t=f"{temp_max}{temp_unit}")
                                    if day_phrase:
                                        a.p(id="day-phrase", _t=day_phrase)
                                    with a.p(id="day-rain-prob"):
                                        a.img(src="icon/raindrops.png", klass="day-rain-prob-icon")
                                        a.span(_t=self.words.rain(rain_prob))



