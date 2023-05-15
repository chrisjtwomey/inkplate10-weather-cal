import datetime as dt
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
                        with a.div(id="hourly-forecasts"):
                            with a.table():
                                with a.thead(klass="forecast-hour"):
                                    with a.tr():
                                        for forecast in hourly_forecasts:
                                            with a.td(klass="hour"):
                                                hour = ""
                                                try:
                                                    hour = forecast["dt"].strftime(
                                                        "%-I"
                                                    )
                                                except ValueError as ve:
                                                    # platform-specific formatting error
                                                    self.log.warning(str(ve))
                                                    hour = forecast["dt"].strftime("%I")

                                                a(
                                                    hour
                                                    + forecast["dt"]
                                                    .strftime("%p")
                                                    .lower()
                                                )

                                with a.tbody(klass="hourly-forecasts-forecast"):
                                    with a.tr():
                                        for forecast in hourly_forecasts:
                                            with a.td():
                                                with a.div(
                                                    klass="hourly-forecast-icon fc-icon"
                                                ):
                                                    a.img(src=forecast["icon"])

                        a.canvas(id="rain-temp-chart", height="100")

                with a.script():
                    a("""
                        Chart.defaults.scale.gridLines.display = false;
                        Chart.defaults.scale.gridLines.color = "rgba(0, 0, 0, 0.3)";
                        Chart.defaults.scale.gridLines.lineWidth = 2;
                        Chart.defaults.scale.ticks.display = false;
                        Chart.defaults.scale.ticks.max = 100;
                        Chart.defaults.global.legend.display = false;
                        Chart.defaults.global.defaultFontColor = "#000";
                        Chart.defaults.global.animation.duration = 0;

                        // Wait until the fonts are all loaded
                        document.fonts.ready.then(() => {{
                            var ctx = document.getElementById('rain-temp-chart').getContext('2d');
                            var chart = new Chart(ctx, {{
                                type: 'bar',
                                data: {{
                                    labels: {0},
                                    datasets: [{{
                                        data: {1},
                                        backgroundColor: 'rgb(0, 0, 0)',
                                        borderColor: 'rgb(0, 0, 0)',
                                        datalabels: {{
                                            display: 'auto',
                                            align: 'top',
                                            anchor: 'end',
                                            clamp: 'true',
                                            backgroundColor: "#FFF",
                                            borderRadius: 4,
                                            font: {{
                                                family: 'Merienda-Regular',
                                                size: 32
                                            }},
                                            display: function(context) {{
                                                var index = context.dataIndex;
                                                var value = context.dataset.data[index];

                                                return value > 0;
                                            }},
                                            formatter: function(value, context) {{
                                                return value + "%";
                                            }}
                                        }},
                                        borderWidth: 3,
                                        stack: 'combined',
                                        rough: {{
                                            roughness: 4,
                                            bowing: 0.2,
                                            fillStyle: 'zigzag',
                                            fillWeight: 1.5,
                                            hachureAngle: 45,
                                            hachureGap: 12
                                        }}
                                    }}, {{
                                        data: {2},
                                        backgroundColor: 'rgba(0, 0, 0, 0)',
                                        borderColor: 'rgb(0, 0, 0)',
                                        datalabels: {{
                                            display: 'auto',
                                            align: 'top',
                                            anchor: 'start',
                                            offset: 12,
                                            backgroundColor: "#FFF",
                                            borderRadius: 4,
                                            font: {{
                                                family: 'Merienda-Regular',
                                                size: 32
                                            }},
                                            formatter: function(value, context) {{
                                                return value + "°C";
                                            }}
                                        }},
                                        rough: {{
                                            roughness: 1,
                                            bowing: 0.1,
                                            fillWeight: 1.5,
                                            hachureAngle: 45,
                                            hachureGap: 12
                                        }},
                                        type: 'line'
                                    }}]
                                }},
                                plugins: [ChartDataLabels, ChartRough]
                            }});
                        }});
                    """.format(hours, precip_percents, temps))
