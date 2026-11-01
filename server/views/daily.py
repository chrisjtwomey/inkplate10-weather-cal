import datetime as dt

from epd_server.page import SkipPage

from .detailed import DetailedPage, wind_arrow, wind_unit_words


def _day_name_cell(a, forecast):
    day = forecast["dt"]
    try:
        date = day.strftime("%-d %b")
    except ValueError:
        date = day.strftime("%d %b").lstrip("0")
    with a.td(klass="day-name-cell"):
        a.div(klass="day-name", _t=day.strftime("%a").upper())
        a.div(klass="day-date", _t=date)


def _temperature_cell(a, temperature, week_min, week_span):
    """The day's range as a bar on the week's scale."""
    low, high, unit = temperature["min"], temperature["max"], temperature["unit"]
    left_pct = round((low - week_min) / week_span * 100, 1)
    right_pct = round((1 - (high - week_min) / week_span) * 100, 1)
    with a.td(klass="day-temp-cell"):
        with a.div(klass="temp-range"):
            a.span(klass="temp-low", _t=str(low) + unit)
            with a.div(klass="temp-bar-track"):
                a.canvas(klass="temp-bar-canvas", **{"data-left": str(left_pct), "data-right": str(right_pct)})
            a.span(klass="temp-high", _t=str(high) + unit)


def _rain_cell(a, forecast):
    with a.td(klass="day-precip-cell"):
        with a.div(klass="day-precip"):
            a.img(src="icon/raindrops.png", klass="precip-icon")
            a.span(klass="precip-value", _t=f"{forecast['rain_probability']}%")


def _wind_cell(a, wind):
    with a.td(klass="day-wind-cell"):
        with a.div(klass="day-wind"):
            wind_arrow(a, wind)
            a.span(klass="wind-speed", _t=str(round(wind["value"])))
            a.span(klass="wind-unit", _t=wind_unit_words(wind))


def _sun_hours_cell(a, forecast):
    with a.td(klass="day-sun-hours-cell"):
        if forecast["hours_of_sun"] is not None:
            with a.div(klass="sun-hours"):
                a.img(src="icon/sun.png", klass="sun-icon")
                a.span(klass="sun-hours-value", _t=f"{forecast['hours_of_sun']:.1f}")
                a.span(klass="sun-hours-unit", _t="hours")


def _sun_row(a, icon, klass, text):
    with a.div(klass="sun-row"):
        a.img(src=icon, klass="sun-icon")
        a.span(klass=klass, _t=text)


def _uv_words(uv):
    return "Low" if uv <= 2 else "Med" if uv <= 5 else "High"


def _sun_cell(a, forecast):
    with a.td(klass="day-sun-cell"):
        with a.div(klass="sun-info"):
            if forecast["sunrise"] and forecast["sunset"]:
                with a.div(klass="sun-times"):
                    _sun_row(a, "icon/sunrise.png", "sun-rise", forecast["sunrise"])
                    _sun_row(a, "icon/sunset.png", "sun-set", forecast["sunset"])
                    if forecast["uv_index"] is not None:
                        _sun_row(a, "icon/uv.png", "sun-set", _uv_words(forecast["uv_index"]))


class DailyPage(DetailedPage):
    requires = ("map_url", "daily_summary", "daily_forecasts")

    def __init__(self, *geometry, **kwargs):
        super().__init__(*geometry, **kwargs)
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
        # Drop any days already in the past (API sometimes returns yesterday)
        today = dt.date.today()
        forecasts = [f for f in kwargs["daily_forecasts"] if f["dt"].date() >= today]
        if not forecasts:
            raise SkipPage("no daily forecasts from today on")

        week_min = min(f["temperature"]["min"] for f in forecasts)
        week_max = max(f["temperature"]["max"] for f in forecasts)
        # Guard against all-same values to avoid division by zero
        week_span = (week_max - week_min) or 1

        has_sun_hours = any(f["hours_of_sun"] is not None for f in forecasts)
        has_sun = any(f["sunrise"] is not None for f in forecasts)

        with a.div(id="daily-body", klass="bg-container"):
            with a.table(id="daily-table", style=f"--daily-row-count:{max(len(forecasts), 1)};"):
                for forecast in forecasts:
                    with a.tr(klass="day-row"):
                        _day_name_cell(a, forecast)
                        with a.td(klass="day-icon-cell"):
                            with a.div(klass="day-icon-wrap"):
                                a.img(src=forecast["icon"], klass="day-icon")
                        _temperature_cell(a, forecast["temperature"], week_min, week_span)
                        _rain_cell(a, forecast)
                        _wind_cell(a, forecast["wind"])
                        if has_sun_hours:
                            _sun_hours_cell(a, forecast)
                        if has_sun:
                            _sun_cell(a, forecast)
