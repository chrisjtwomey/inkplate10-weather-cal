import datetime as dt
from airium import Airium
from .page import Page


def wind_unit_words(wind: dict, words) -> str:
    return words["kmh"] if wind["unit"] == "kmh" else words["mph"]


def wind_arrow(a, wind: dict) -> None:
    """The arrow for ``wind``: it points the way the wind blows, and grows with its speed."""
    speed_kmh = wind["value"] if wind["unit"] == "kmh" else wind["value"] * 1.609
    size = round(2.5 + 2.5 * min(speed_kmh / 80.0, 1.0) ** 0.5, 2)
    a.img(
        src="icon/wind-arrow.png",
        klass="wind-arrow",
        style=f"transform: rotate({(wind['direction_degrees'] + 180) % 360}deg); width: calc(var(--inner-vw) * {size}); height: calc(var(--inner-vw) * {size});",
    )


class DetailedPage(Page):
    def __init__(self, *geometry, **kwargs):
        super().__init__("detailed", *geometry, **kwargs)

    def _title(self) -> str:
        return self.words["title_detailed"]

    def _css_links(self, a):
        a.link(rel="stylesheet", href="styles.css")
        a.link(rel="stylesheet", href="detailed.css")

    def _script_tags(self, a):
        pass

    def _render_body(self, a, **kwargs):
        pass

    def template(self, **kwargs):
        self.airium = Airium()

        map_url = self.picture_url(kwargs)
        daily_summary = kwargs["daily_summary"]

        a = self.airium
        now = dt.datetime.now()
        now_date = now.date()
        self.log.info("Rendering %s page for %s", self.name, now_date)

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(charset="utf-8")
                a.meta(name="viewport", content="width=device-width, initial-scale=1")
                a.title(_t=self._title())
                self._css_links(a)
                self._script_tags(a)

            with a.body(style=self.layout_css_variables()):
                with a.div(klass="inner-canvas-outer"):
                    with a.div(klass="inner-canvas"):
                        with a.div(klass="inner-canvas-content"):
                            with a.div(klass="bg-container"):
                                with a.div(id="top-banner", klass="container"):
                                    with a.div(id="date-banner"):
                                        a.h3(
                                            id="date",
                                            klass="numcircle text-center",
                                            _t=str(now_date.day),
                                        )
                                        a.h3(
                                            id="month",
                                            klass="month text-center text-uppercase",
                                            _t=self.words.month(now_date),
                                        )

                                    a.h4(
                                        id="temp",
                                        klass="numcircle text-center",
                                        _t=str(daily_summary["temperature"]["max"])
                                        + daily_summary["temperature"]["unit"],
                                    )

                                    with a.div(id="icon-container", klass="numcircle"):
                                        a.img(src=daily_summary["icon"])

                            with a.div(id="map-container", **{"data-picture": "main"}):
                                a.img(src=map_url, id="map")

                            self._render_body(a, **kwargs)
