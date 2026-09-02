import datetime as dt
from airium import Airium
from .detailed import DetailedPage


class DailyPage(DetailedPage):
    requires = ("map_url", "daily_summary", "daily_forecasts")

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
        self.name = "daily"

    def _title(self):
        return "Daily Forecast"

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="daily.css")

    def _script_tags(self, a):
        a.script(src="rough.iife.min.js")
        with a.script():
            a("""
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('canvas.temp-bar-canvas').forEach(function (canvas) {
        var leftPct  = parseFloat(canvas.getAttribute('data-left'))  / 100;
        var rightPct = parseFloat(canvas.getAttribute('data-right')) / 100;
        var w = canvas.offsetWidth;
        var h = canvas.offsetHeight;
        canvas.width  = w;
        canvas.height = h;
        var x1    = w * leftPct;
        var x2    = w * (1 - rightPct);
        var pillW = Math.max(x2 - x1, 2);
        var pillH = h / 3;
        var y0 = (h - pillH) / 2, y1 = y0 + pillH;
        var r  = Math.min((y1 - y0) / 2, pillW / 2);
        var path = [
            'M', x1 + r, y0,
            'H', x2 - r,
            'Q', x2, y0,   x2, y0 + r,
            'V', y1 - r,
            'Q', x2, y1,   x2 - r, y1,
            'H', x1 + r,
            'Q', x1, y1,   x1, y1 - r,
            'V', y0 + r,
            'Q', x1, y0,   x1 + r, y0,
            'Z'
        ].join(' ');
        var rc = rough.canvas(canvas);
        rc.path(path, {
            fill: '#000',
            fillStyle:    'zigzag',
            hachureAngle: 45,
            hachureGap:   5,
            roughness:    0.8,
            bowing:       1,
            strokeWidth:  1.3
        });
    });
});
            """)

    def _render_body(self, a, **kwargs):
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
        has_sun_hours = any(f["hours_of_sun"] is not None for f in daily_forecasts)
        has_sun = any(
            f["sunrise"] is not None
            for f in daily_forecasts
        )

        # ── Bottom half: 5-day forecast table ────────────────────────
        with a.div(id="daily-body", klass="bg-container"):
            with a.table(
                id="daily-table",
                style=f"--daily-row-count:{max(len(daily_forecasts), 1)};",
            ):
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
                            span = week_max - week_min
                            left_pct  = round((forecast["temperature"]["min"] - week_min) / span * 100, 1)
                            right_pct = round((1 - (forecast["temperature"]["max"] - week_min) / span) * 100, 1)
                            with a.div(klass="temp-range"):
                                a.span(
                                    klass="temp-low",
                                    _t=str(forecast["temperature"]["min"])
                                    + temp_unit,
                                )
                                with a.div(klass="temp-bar-track"):
                                    a.canvas(
                                        klass="temp-bar-canvas",
                                        **{"data-left": str(left_pct), "data-right": str(right_pct)}
                                    )
                                a.span(
                                    klass="temp-high",
                                    _t=str(forecast["temperature"]["max"])
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

                        # Hours of sun (only rendered when any day has sun hours data)
                        if has_sun_hours:
                            with a.td(klass="day-sun-hours-cell"):
                                if forecast["hours_of_sun"] is not None:
                                    with a.div(klass="sun-hours"):
                                        a.img(
                                            src="icon/sun.png",
                                            klass="sun-icon",
                                        )
                                        a.span(
                                            klass="sun-hours-value",
                                            _t=f"{forecast['hours_of_sun']:.1f}",
                                        )
                                        a.span(
                                            klass="sun-hours-unit",
                                            _t="hours",
                                        )

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
                                            if has_uv and forecast["uv_index"] is not None:
                                                uv = forecast["uv_index"]
                                                uv_label = "Low" if uv <= 2 else "Med" if uv <= 5 else "High"
                                                with a.div(klass="sun-row"):
                                                    a.img(
                                                        src="icon/uv.png",
                                                        klass="sun-icon",
                                                    )
                                                    a.span(
                                                        klass="sun-set",
                                                        _t=uv_label,
                                                    )