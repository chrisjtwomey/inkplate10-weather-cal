import datetime as dt
from airium import Airium
from .detailed import DetailedPage


class HourlyPage(DetailedPage):
    def __init__(
        self,
        width,
        height,
    ):
        super().__init__(width, height)
        self.name = "hourly"

    def _title(self) -> str:
        return "Hourly"

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="hourly.css")

    def _script_tags(self, a):
        a.script(type="text/javascript", src="https://unpkg.com/chart.js@2.8.0")
        a.script(type="text/javascript", src="https://unpkg.com/roughjs@3.1.0/dist/rough.js")
        a.script(
            type="text/javascript",
            src="https://unpkg.com/chartjs-plugin-datalabels@1.0.0",
        )
        a.script(
            type="text/javascript",
            src="https://unpkg.com/chartjs-plugin-rough@latest/dist/chartjs-plugin-rough.min.js",
        )

    def _render_body(self, a, **kwargs):
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

        temp_unit = hourly_forecasts[0]["temperature"]["unit"]
        wind_unit_raw = hourly_forecasts[0]["wind"]["unit"]
        wind_unit_display = "kph" if wind_unit_raw == "kmh" else "mph"

        with a.div(klass="bg-container"):
            with a.div(id="bottom-banner", klass="container"):
                with a.table(id="forecast-table"):
                    # Icon row
                    with a.tr():
                        with a.td(klass="legend-cell"):
                            a.canvas(klass="legend-divider")
                        for forecast in hourly_forecasts:
                            with a.td(klass="forecast-cell"):
                                with a.div(klass="forecast-icon"):
                                    a.img(src=forecast["icon"])

                    # Hour row — show every second label to stay readable at distance
                    with a.tr():
                        with a.td(klass="legend-cell"):
                            a.img(src="icon/wall-clock.png", klass="legend-icon")
                            a.canvas(klass="legend-divider")
                        for i, forecast in enumerate(hourly_forecasts):
                            hour = ""
                            try:
                                hour = forecast["dt"].strftime("%-I")
                            except ValueError as ve:
                                hour = forecast["dt"].strftime("%I")
                            hour = hour + forecast["dt"].strftime("%p").lower()

                            with a.td(klass="forecast-cell"):
                                with a.div(klass="forecast-hour"):
                                    show_hour = len(hourly_forecasts) <= 6 or i % 2 == 0
                                    a(hour if show_hour else "")

                    # Temperature row — hide repeated adjacent values
                    prev_temp = None
                    with a.tr():
                        with a.td(klass="legend-cell"):
                            a.img(src="icon/thermometer.png", klass="legend-icon")
                            a.span(klass="legend-unit", _t=temp_unit)
                            a.canvas(klass="legend-divider")
                        for forecast in hourly_forecasts:
                            temp_val = forecast["temperature"]["value"]
                            with a.td(klass="forecast-cell"):
                                with a.div(klass="forecast-temp"):
                                    a(str(temp_val) + "°" if temp_val != prev_temp else "")
                            prev_temp = temp_val

                    # Wind direction and speed row — hide repeated adjacent speeds
                    prev_wind_speed = None
                    with a.tr():
                        with a.td(klass="legend-cell"):
                            a.img(src="icon/wind.png", klass="legend-icon")
                            a.span(klass="legend-unit", _t=wind_unit_display)
                            a.canvas(klass="legend-divider")
                        for forecast in hourly_forecasts:
                            deg = forecast["wind"]["direction_degrees"]
                            speed_val = forecast["wind"]["value"]
                            speed = str(round(speed_val))
                            # Scale arrow between 2.5vw–6vw based on speed (normalised to km/h)
                            speed_kmh = speed_val if forecast["wind"]["unit"] == "kmh" else speed_val * 1.609
                            arrow_size = round(2.5 + 2.5 * min(speed_kmh / 80.0, 1.0) ** 0.5, 2)
                            with a.td(klass="forecast-cell"):
                                with a.div(klass="forecast-wind"):
                                    a.img(
                                        src="icon/wind-arrow.png",
                                        klass="wind-arrow",
                                        style=f"transform: rotate({(deg + 180) % 360}deg); width: {arrow_size}vw; height: {arrow_size}vw;",
                                    )
                                    a.span(klass="wind-speed", _t=speed if speed != prev_wind_speed else "")
                            prev_wind_speed = speed

                    # Precipitation bar row — hide repeated adjacent labels, and only on even columns
                    prev_precip = None
                    with a.tr():
                        with a.td(klass="legend-cell"):
                            a.img(src="icon/raindrops.png", klass="legend-icon")
                            a.canvas(klass="legend-divider")
                        for i, forecast in enumerate(hourly_forecasts):
                            precip = forecast["rain_probability"]
                            show_even = len(hourly_forecasts) <= 6 or i % 2 == 0
                            show_label = show_even and precip != prev_precip
                            with a.td(klass="forecast-cell"):
                                a.canvas(
                                    klass="precip-canvas",
                                    data_precip=str(precip),
                                    data_show_label="true" if show_label else "false",
                                )
                            prev_precip = precip

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
                        var pad  = Math.round(w * 0.05);
                        var barW = w - pad * 2;

                        var rc = rough.canvas(canvas);
                        rc.rectangle(pad, h - barH, barW, barH, {
                            fill:         '#aaa',
                            fillStyle:    'zigzag',
                            hachureAngle: 45,
                            hachureGap:   5,
                            roughness:    1,
                            bowing:       1,
                            strokeWidth:  2
                        });

                        var ctx      = canvas.getContext('2d');
                        // Fixed font size for all labels
                        var fontSize = 24;
                        ctx.font      = 'bold ' + fontSize + 'px Merienda-Regular, sans-serif';
                        ctx.textAlign = 'center';

                        // Always render label above bar, except >= 80% where it would clip
                        var showLabel = canvas.getAttribute('data_show_label') !== 'false';
                        var label  = pct + '%';
                        if (showLabel && pct < 80) {
                            var labelY = h - barH - 6;
                            ctx.fillStyle = '#000';
                            ctx.fillText(label, w / 2, labelY);
                        }
                    });

                    var dividers = document.querySelectorAll('.legend-divider');
                    var dashLen  = 10;
                    var gapLen   = 6;
                    var cycle    = dashLen + gapLen;
                    var firstTop = dividers.length > 0 ? dividers[0].getBoundingClientRect().top : 0;

                    dividers.forEach(function(canvas) {
                        var w = canvas.offsetWidth || 8;
                        var h = canvas.offsetHeight || 60;
                        canvas.width  = w;
                        canvas.height = h;
                        var rc    = rough.canvas(canvas);
                        var x     = w / 2;
                        var phase = (canvas.getBoundingClientRect().top - firstTop) % cycle;
                        var y     = -phase;
                        while (y < h) {
                            var segStart = Math.max(y, 0);
                            var segEnd   = Math.min(y + dashLen, h);
                            if (segEnd > segStart) {
                                rc.line(x, segStart, x, segEnd, {
                                    roughness:   2.5,
                                    stroke:      '#aaa',
                                    strokeWidth: 1.5
                                });
                            }
                            y += cycle;
                        }
                    });
                };
            """)
