import datetime as dt
from airium import Airium
from .page import Page


class DetailedPage(Page):
    def __init__(self, width, height):
        super().__init__("detailed", width, height)

    def _title(self):
        return "Detailed"

    def _css_links(self, a):
        a.link(rel="stylesheet", href="styles.css")

    def _script_tags(self, a):
        pass

    def _render_body(self, a, **kwargs):
        pass

    def template(self, **kwargs):
        self.airium = Airium()

        map_url = kwargs["map_url"]
        daily_summary = kwargs["daily_summary"]

        a = self.airium
        now = dt.datetime.now()
        now_date = now.date()
        self.log.info("Rendering %s page for %s", self.name, now_date)

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(
                    charset="utf-8",
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                a.title(_t=self._title())
                self._css_links(a)
                self._script_tags(a)

            with a.body():
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
                                _t=now_date.strftime("%B"),
                            )

                        a.h4(
                            id="temp",
                            klass="numcircle text-center",
                            _t=str(daily_summary["temperature"]["value"])
                            + daily_summary["temperature"]["unit"],
                        )

                        with a.div(id="icon-container", klass="numcircle"):
                            a.img(src=daily_summary["icon"])

                with a.div(id="map-container"):
                    a.img(src=map_url, id="map")

                self._render_body(a, **kwargs)
