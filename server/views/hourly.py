from epd_server.page import SkipPage

from .detailed import DetailedPage, wind_arrow, wind_unit_words


def _legend(a, icon, unit=None):
    with a.td(klass="legend-cell"):
        a.img(src=icon, klass="legend-icon")
        if unit is not None:
            a.span(klass="legend-unit", _t=unit)
        a.canvas(klass="legend-divider")


def _every_column_fits(forecasts):
    """Past 6 columns, only every second one has room for a label."""
    return len(forecasts) <= 6


def _icon_row(a, forecasts):
    with a.tr():
        with a.td(klass="legend-cell"):
            a.canvas(klass="legend-divider")
        for forecast in forecasts:
            with a.td(klass="forecast-cell"):
                with a.div(klass="forecast-icon"):
                    a.img(src=forecast["icon"])


def _hour_row(a, forecasts, words):
    with a.tr():
        _legend(a, "icon/wall-clock.png")
        for i, forecast in enumerate(forecasts):
            with a.td(klass="forecast-cell"):
                with a.div(klass="forecast-hour"):
                    a(words.hour(forecast["dt"]) if _every_column_fits(forecasts) or i % 2 == 0 else "")


def _temperature_row(a, forecasts):
    """Each temperature, blank where it repeats the one before."""
    previous = None
    with a.tr():
        _legend(a, "icon/thermometer.png", forecasts[0]["temperature"]["unit"])
        for forecast in forecasts:
            value = forecast["temperature"]["value"]
            with a.td(klass="forecast-cell"):
                with a.div(klass="forecast-temp"):
                    a(str(value) + "°" if value != previous else "")
            previous = value


def _wind_row(a, forecasts, words):
    """Each wind's arrow and speed, the speed blank where it repeats the one before."""
    previous = None
    with a.tr():
        _legend(a, "icon/wind.png", wind_unit_words(forecasts[0]["wind"], words))
        for forecast in forecasts:
            speed = str(round(forecast["wind"]["value"]))
            with a.td(klass="forecast-cell"):
                with a.div(klass="forecast-wind"):
                    wind_arrow(a, forecast["wind"])
                    a.span(klass="wind-speed", _t=speed if speed != previous else "")
            previous = speed


def _rain_row(a, forecasts, words):
    """Each chance of rain as a bar, labelled unless the label repeats the one before."""
    previous = None
    with a.tr(klass="precip-row"):
        _legend(a, "icon/raindrops.png")
        for i, forecast in enumerate(forecasts):
            chance = forecast["rain_probability"]
            show_label = (_every_column_fits(forecasts) or i % 2 == 0) and chance != previous
            with a.td(klass="forecast-cell"):
                a.canvas(
                    klass="precip-canvas",
                    **{"data-precip": str(chance), "data-label": words.percent(chance)},
                    data_show_label="true" if show_label else "false",
                )
            previous = chance


class HourlyPage(DetailedPage):
    requires = ("map_url", "daily_summary", "hourly_forecasts")

    def __init__(self, *geometry, **kwargs):
        super().__init__(*geometry, **kwargs)
        self.name = "hourly"

    def _title(self) -> str:
        return self.words["title_hourly"]

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="hourly.css")

    def _script_tags(self, a):
        a.script(src="rough.iife.min.js")

    def _render_body(self, a, **kwargs):
        forecasts = kwargs["hourly_forecasts"]
        if not forecasts:
            raise SkipPage("no hourly forecasts")
        with a.div(id="bottom-banner", klass="container"):
            with a.table(id="forecast-table", style=f"--hourly-columns:{len(forecasts)};"):
                _icon_row(a, forecasts)
                _hour_row(a, forecasts, self.words)
                _temperature_row(a, forecasts)
                _wind_row(a, forecasts, self.words)
                _rain_row(a, forecasts, self.words)
        self._bars_script(a)

    def _bars_script(self, a):
        with a.script():
            a("""
                window.onload = function() {
                    var bars = document.querySelectorAll('.precip-canvas');
                    bars.forEach(function(canvas) {
                        var pct  = parseInt(canvas.getAttribute('data-precip'), 10);
                        var rect = canvas.getBoundingClientRect();
                        var w    = Math.max(1, Math.round(rect.width || canvas.parentElement.offsetWidth || 80));
                        var h    = Math.max(40, Math.round(rect.height || canvas.parentElement.offsetHeight || 120));
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
                        // Scale label font with the available row height.
                        var fontSize = Math.max(12, Math.round(h * 0.1));
                        ctx.font      = 'bold ' + fontSize + 'px Merienda, sans-serif';
                        ctx.textAlign = 'center';

                        // Above the bar, or inside it on white when the top of the canvas would cut it off.
                        var showLabel = canvas.getAttribute('data_show_label') !== 'false';
                        var label  = canvas.getAttribute('data-label');
                        if (showLabel) {
                            var labelY = h - barH - 6;
                            if (labelY - fontSize < 0) {
                                labelY = h - barH + fontSize + 10;
                                var labelW = ctx.measureText(label).width;
                                ctx.fillStyle = '#fff';
                                ctx.fillRect((w - labelW) / 2 - 4, labelY - fontSize - 1, labelW + 8, fontSize + 7);
                            }
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
