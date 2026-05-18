import datetime as dt
from airium import Airium
from .page import Page


class DailyPage(Page):
    def __init__(self, width, height):
        super().__init__("daily", width, height)

    def template(self, **kwargs):
        self.airium = Airium()

        map_url = kwargs["map_url"]
        daily_summary = kwargs["daily_summary"]
        daily_forecasts = kwargs["daily_forecasts"]

        # Drop any days already in the past (API sometimes returns yesterday)
        now_date = dt.date.today()
        daily_forecasts = [f for f in daily_forecasts if f["dt"].date() >= now_date]

        # Compute week-wide min/max for scaling temperature range bars
        week_min = min(f["temperature"]["min"] for f in daily_forecasts)
        week_max = max(f["temperature"]["max"] for f in daily_forecasts)
        # Guard against all-same values to avoid division by zero
        if week_max == week_min:
            week_max = week_min + 1

        temp_unit = daily_forecasts[0]["temperature"]["unit"]
        wind_unit_raw = daily_forecasts[0]["wind"]["unit"]
        wind_unit_display = "kph" if wind_unit_raw == "kmh" else "mph"

        has_uv = any(f["uv_index"] is not None for f in daily_forecasts)
        has_sun = any(
            f["sunrise"] is not None or f["hours_of_sun"] is not None
            for f in daily_forecasts
        )

        a = self.airium
        self.log.info("Rendering daily page for %s", now_date)

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(
                    charset="utf-8",
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                a.title(_t="Daily Forecast")
                a.link(rel="stylesheet", href="styles.css")
                a.link(rel="stylesheet", href="daily.css")
                a.script(
                    type="text/javascript",
                    src="https://unpkg.com/roughjs@3.1.0/dist/rough.js",
                )

            with a.body():
                # ── Top half: same as today page ─────────────────────────────
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

                # ── Bottom half: 5-day forecast table ────────────────────────
                with a.div(id="daily-body", klass="bg-container"):
                    with a.table(id="daily-table"):
                        for forecast in daily_forecasts:
                            day_name = forecast["dt"].strftime("%a").upper()
                            try:
                                day_date = forecast["dt"].strftime("%-d %b")
                            except ValueError:
                                day_date = forecast["dt"].strftime("%d %b").lstrip("0")

                            deg = forecast["wind"]["direction_degrees"]
                            speed_val = forecast["wind"]["value"]
                            speed_kmh = (
                                speed_val
                                if wind_unit_raw == "kmh"
                                else speed_val * 1.609
                            )
                            arrow_size = round(
                                2.5 + 2.5 * min(speed_kmh / 80.0, 1.0) ** 0.5, 2
                            )

                            with a.tr(klass="day-row"):
                                # Day name + date
                                with a.td(klass="day-name-cell"):
                                    a.div(klass="day-name", _t=day_name)
                                    a.div(klass="day-date", _t=day_date)

                                # Weather icon
                                with a.td(klass="day-icon-cell"):
                                    with a.div(klass="day-icon-wrap"):
                                        a.img(src=forecast["icon"], klass="day-icon")

                                # Temperature range bar
                                with a.td(klass="day-temp-cell"):
                                    with a.div(klass="temp-range"):
                                        a.span(
                                            klass="temp-high",
                                            _t=str(forecast["temperature"]["max"])
                                            + temp_unit,
                                        )
                                        a.canvas(
                                            klass="temp-bar",
                                            data_min=str(
                                                forecast["temperature"]["min"]
                                            ),
                                            data_max=str(
                                                forecast["temperature"]["max"]
                                            ),
                                            data_week_min=str(week_min),
                                            data_week_max=str(week_max),
                                        )
                                        a.span(
                                            klass="temp-low",
                                            _t=str(forecast["temperature"]["min"])
                                            + temp_unit,
                                        )

                                # Precipitation: icon + percentage
                                with a.td(klass="day-precip-cell"):
                                    with a.div(klass="day-precip"):
                                        a.img(
                                            src="icon/raindrops.png",
                                            klass="precip-icon",
                                        )
                                        a.span(
                                            klass="precip-value",
                                            _t=f"{forecast['rain_probability']}%",
                                        )

                                # Wind
                                with a.td(klass="day-wind-cell"):
                                    with a.div(klass="day-wind"):
                                        a.img(
                                            src="icon/wind-arrow.png",
                                            klass="wind-arrow",
                                            style=(
                                                f"transform: rotate({(deg + 180) % 360}deg);"
                                                f" width: {arrow_size}vw;"
                                                f" height: {arrow_size}vw;"
                                            ),
                                        )
                                        a.span(
                                            klass="wind-speed",
                                            _t=str(round(speed_val)),
                                        )
                                        a.span(
                                            klass="wind-unit", _t=wind_unit_display
                                        )

                                # UV index (only rendered when any day has UV data)
                                if has_uv:
                                    with a.td(klass="day-uv-cell"):
                                        if forecast["uv_index"] is not None:
                                            with a.div(klass="uv-index"):
                                                a.img(
                                                    src="icon/sun.png",
                                                    klass="uv-icon",
                                                )
                                                a.span(
                                                    klass="uv-value",
                                                    _t=str(forecast["uv_index"]),
                                                )
                                                a.small(klass="uv-label", _t="UV")

                                # Sunrise / sunset / hours of sun (only when data available)
                                if has_sun:
                                    with a.td(klass="day-sun-cell"):
                                        with a.div(klass="sun-info"):
                                            if (
                                                forecast["sunrise"]
                                                and forecast["sunset"]
                                            ):
                                                with a.div(klass="sun-times"):
                                                    with a.div(klass="sun-row"):
                                                        a.img(
                                                            src="icon/sunrise.png",
                                                            klass="sun-icon",
                                                        )
                                                        a.span(
                                                            klass="sun-rise",
                                                            _t=forecast["sunrise"],
                                                        )
                                                    with a.div(klass="sun-row"):
                                                        a.img(
                                                            src="icon/sunset.png",
                                                            klass="sun-icon",
                                                        )
                                                        a.span(
                                                            klass="sun-set",
                                                            _t=forecast["sunset"],
                                                        )
                                            if forecast["hours_of_sun"] is not None:
                                                a.div(
                                                    klass="sun-hours",
                                                    _t=f"{forecast['hours_of_sun']:.1f}h ☀",
                                                )

                with a.script():
                    a("""
                        window.onload = function() {

                            // ── Temperature range bars ──────────────────────────────────
                            var tempBars = document.querySelectorAll('.temp-bar');
                            tempBars.forEach(function(canvas) {
                                var w       = canvas.offsetWidth  || 160;
                                var h       = canvas.offsetHeight || 18;
                                canvas.width  = w;
                                canvas.height = h;

                                var dayMin  = parseInt(canvas.getAttribute('data_min'),      10);
                                var dayMax  = parseInt(canvas.getAttribute('data_max'),      10);
                                var wkMin   = parseInt(canvas.getAttribute('data_week_min'), 10);
                                var wkMax   = parseInt(canvas.getAttribute('data_week_max'), 10);
                                var span    = wkMax - wkMin;

                                var x1   = Math.round((dayMin - wkMin) / span * w);
                                var x2   = Math.round((dayMax - wkMin) / span * w);
                                var barW = Math.max(x2 - x1, 4);
                                var barH = Math.round(h * 0.55);
                                var barY = Math.round((h - barH) / 2);

                                var rc = rough.canvas(canvas);
                                rc.rectangle(x1, barY, barW, barH, {
                                    fill:        'black',
                                    fillStyle:    'zigzag',
                                    hachureAngle: 45,
                                    hachureGap:   5,
                                    roughness:    1,
                                    bowing:       1,
                                    strokeWidth:  2
                                });
                            });

                        };
                    """)
