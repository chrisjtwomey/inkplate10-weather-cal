import datetime as dt
from airium import Airium
from .page import Page


class CalendarPage(Page):
    def __init__(
        self,
        width,
        height,
    ):
        super().__init__("calendar", width, height)

    def template(
        self,
        **kwargs,
    ):
        self.airium = Airium()

        map_url = kwargs["map_url"]
        daily_summary = kwargs["daily_summary"]
        hourly_forecasts = kwargs["hourly_forecasts"]

        hours = []
        temps = []
        precip_percents = []
        for forecast in hourly_forecasts:
            hour = ""
            try:
                hour = forecast["dt"].strftime("%-I")
            except ValueError as ve:
                # platform-specific formatting error
                #self.log.warning(str(ve))
                hour = forecast["dt"].strftime("%I")

            hour = hour + forecast["dt"].strftime("%p").lower()
            hours.append(hour)
            temps.append(forecast["temperature"]["value"])
            precip_percents.append(forecast["rain_probability"])

        a = self.airium
        now = dt.datetime.now()
        self.log.info("Time synchronised to %s", now)
        now_date = now.date()

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(
                    charset="utf-8",
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                a.title(_t="Calendar")
                a.link(rel="stylesheet", href="styles.css")
                a.script(type="text/javascript", src="https://unpkg.com/chart.js@2.8.0")
                a.script(type="text/javascript", src="https://unpkg.com/roughjs@3.1.0/dist/rough.js")
                a.script(type="text/javascript", src="https://unpkg.com/chartjs-plugin-datalabels@1.0.0")
                a.script(type="text/javascript", src="https://unpkg.com/chartjs-plugin-rough@latest/dist/chartjs-plugin-rough.min.js")

            with a.body():
                with a.div(klass="bg-container"):
                    with a.div(id="top-banner", klass="container"):
                        with a.div():
                            a.h3(
                                id="date",
                                klass="numcircle text-center",
                                _t=now_date.day,
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

                with a.div(klass="bg-container"):
                    with a.div(id="bottom-banner", klass="container"):
                        with a.table(id="forecast-table"):
                            # Icon row
                            with a.tr():
                                for forecast in hourly_forecasts:
                                    with a.td(klass="forecast-cell"):
                                        with a.div(klass="forecast-icon"):
                                            a.img(src=forecast["icon"])

                            # Hour row
                            with a.tr():
                                for forecast in hourly_forecasts:
                                    hour = ""
                                    try:
                                        hour = forecast["dt"].strftime("%-I")
                                    except ValueError as ve:
                                        hour = forecast["dt"].strftime("%I")
                                    hour = hour + forecast["dt"].strftime("%p").lower()

                                    with a.td(klass="forecast-cell"):
                                        with a.div(klass="forecast-hour"):
                                            a(hour)

                            # Temperature row
                            with a.tr():
                                for forecast in hourly_forecasts:
                                    with a.td(klass="forecast-cell"):
                                        with a.div(klass="forecast-temp"):
                                            a(str(forecast["temperature"]["value"]) + "°")

                            # Precipitation bar row
                            with a.tr():
                                for forecast in hourly_forecasts:
                                    precip = forecast["rain_probability"]
                                    with a.td(klass="forecast-cell"):
                                        a.canvas(
                                            klass="precip-canvas",
                                            data_precip=str(precip),
                                        )

                with a.script():
                    a("""
                        window.onload = function() {
                            var bars = document.querySelectorAll('.precip-canvas');
                            bars.forEach(function(canvas) {
                                var pct  = parseInt(canvas.getAttribute('data_precip'), 10);
                                var w    = canvas.parentElement.offsetWidth || 80;
                                var h    = 120;
                                canvas.width  = w;
                                canvas.height = h;

                                var barH = Math.max(2, Math.round(h * pct / 100));
                                var pad  = Math.round(w * 0.1);
                                var barW = w - pad * 2;

                                var rc = rough.canvas(canvas);
                                rc.rectangle(pad, h - barH, barW, barH, {
                                    fill:         'black',
                                    fillStyle:    'zigzag',
                                    hachureAngle: 45,
                                    hachureGap:   8,
                                    roughness:    1.5,
                                    bowing:       1.5,
                                    strokeWidth:  1.5
                                });

                                var ctx      = canvas.getContext('2d');
                                // Match ~3vw font size used in the rest of the table
                                var fontSize = Math.max(14, Math.round(w * 0.18));
                                ctx.font      = 'bold ' + fontSize + 'px Merienda-Regular, sans-serif';
                                ctx.textAlign = 'center';

                                // Place label inside bar if there's room, above bar otherwise
                                var labelY   = h - barH / 2 + fontSize * 0.35;
                                var inBar    = barH > fontSize + 8;
                                if (!inBar) {
                                    // above the bar, black text
                                    labelY = h - barH - 6;
                                    ctx.fillStyle = '#000';
                                    ctx.fillText(pct + '%', w / 2, labelY);
                                } else {
                                    // inside bar — stroke in black first for outline, fill white
                                    ctx.strokeStyle = '#000';
                                    ctx.lineWidth   = 3;
                                    ctx.lineJoin    = 'round';
                                    ctx.strokeText(pct + '%', w / 2, labelY);
                                    ctx.fillStyle = '#fff';
                                    ctx.fillText(pct + '%', w / 2, labelY);
                                }
                            });
                        };
                    """)
