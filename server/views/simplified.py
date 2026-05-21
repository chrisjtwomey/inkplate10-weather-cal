from airium import Airium
from .page import Page


def _uv_category(uv):
    if uv <= 2:
        return "Low"
    elif uv <= 5:
        return "Moderate"
    elif uv <= 7:
        return "High"
    elif uv <= 10:
        return "Very High"
    else:
        return "Extreme"


def _wind_direction(deg):
    names = [
        "Northerly", "North-easterly", "Easterly", "South-easterly",
        "Southerly", "South-westerly", "Westerly", "North-westerly",
    ]
    return names[round(deg / 45) % 8]


def _fmt_hours(h):
    if h is None:
        return None
    v = int(h) if h == int(h) else round(h, 1)
    return f"{v} hr{'s' if v != 1 else ''}"


class SimplifiedPage(Page):
    def __init__(self, width, height):
        super().__init__("simplified", width, height)

    def _css_links(self, a):
        a.link(rel="stylesheet", href="styles.css")
        a.link(rel="stylesheet", href="simplified.css")

    def _script_tags(self, a):
        pass  # subclasses may add extra <script> tags in <head>

    def _render_stats(self, a, forecast):
        rain_prob = forecast["rain_probability"]
        uv_idx = forecast.get("uv_index")
        wind_val = forecast["wind"]["value"]
        wind_unit = forecast["wind"]["unit"]
        wind_deg = forecast["wind"]["direction_degrees"]
        hours_of_sun = forecast.get("hours_of_sun")
        hours_of_rain = forecast.get("hours_of_rain")

        wind_unit_display = "kph" if wind_unit == "kmh" else "mph"

        with a.div(id="day-stats"):

            # Rain — row 1 (no indent)
            with a.div(klass="stat-row stat-rain"):
                a.img(src="icon/raindrops.png", klass="stat-icon")
                with a.div(klass="stat-text"):
                    rain_hrs = _fmt_hours(hours_of_rain)
                    if rain_hrs and hours_of_rain > 0:
                        a.span(klass="stat-primary", _t=f"{rain_hrs} of rain")
                        a.span(klass="stat-secondary", _t=f"{rain_prob}% chance of rain")
                    else:
                        a.span(klass="stat-primary", _t=f"{rain_prob}% chance of rain")

            # UV — row 2 (indented)
            if uv_idx is not None:
                with a.div(klass="stat-row stat-uv"):
                    a.img(src="icon/sun.png", klass="stat-icon")
                    with a.div(klass="stat-text"):
                        sun_hrs = _fmt_hours(hours_of_sun)
                        if sun_hrs is not None:
                            a.span(klass="stat-primary", _t=f"{sun_hrs} of sunshine")
                            a.span(klass="stat-secondary", _t=f"UV Index {uv_idx}")
                        else:
                            a.span(klass="stat-primary", _t=f"UV Index {uv_idx}")
                            a.span(klass="stat-secondary", _t=_uv_category(uv_idx))

            # Wind — row 3 (most indented)
            with a.div(klass="stat-row stat-wind"):
                a.img(
                    src="icon/wind.png",
                    klass="stat-icon wind",
                )
                with a.div(klass="stat-text"):
                    a.span(klass="stat-primary", _t=f"{round(wind_val)} {wind_unit_display}")
                    a.span(klass="stat-secondary", _t=_wind_direction(wind_deg))

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
        uv_idx = forecast.get("uv_index")
        wind_val = forecast["wind"]["value"]
        wind_unit = forecast["wind"]["unit"]
        wind_deg = forecast["wind"]["direction_degrees"]
        day_phrase = forecast.get("day_phrase")

        wind_unit_display = "kph" if wind_unit == "kmh" else "mph"
        speed_kmh = wind_val if wind_unit == "kmh" else wind_val * 1.609

        alerts = []
        if rain_prob >= 70:
            alerts.append(f"High chance of rain ({rain_prob}%)")
        if uv_idx is not None and uv_idx >= 6:
            label = _uv_category(uv_idx)
            alerts.append(f"{label} UV index ({uv_idx})")
        if speed_kmh >= 50:
            alerts.append(f"Strong winds ({round(wind_val)} {wind_unit_display})")

        # Fixed temperature scale so the pill's position is consistent.
        # Covers -10…40°C (14–104°F) — the same pill proportions work for both.
        if "F" in temp_unit.upper():
            _scale_min, _scale_max = 14, 104
        else:
            _scale_min, _scale_max = -10, 40

        self.log.info("Rendering %s page for %s", self.name, forecast_dt.date())

        try:
            date_str = forecast_dt.strftime("%A, %B %-d")
        except ValueError:
            date_str = forecast_dt.strftime("%A, %B %d").replace(" 0", " ")

        a("<!DOCTYPE html>")
        with a.html(lang="en"):
            with a.head():
                a.meta(
                    charset="utf-8",
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                a.title(_t="Day Forecast")
                self._css_links(a)
                self._script_tags(a)

            with a.body():
                # ── Map ──────────────────────────────────────────────────
                with a.div(id="day-map-wrapper"):
                    with a.div(id="map-container"):
                        a.img(src=map_url, id="map")

                # ── Content section ───────────────────────────────────────
                with a.div(id="day-body", klass="bg-container"):

                    # ── Hero: icon → date → temperature → phrase ──
                    with a.div(id="day-hero"):
                        a.img(src=forecast["icon"], id="day-icon")
                        a.p(id="day-date", _t=date_str)
                        a.p(id="day-temp-main", _t=f"{temp_max}{temp_unit}")
                        if day_phrase:
                            a.p(id="day-phrase", _t=day_phrase)

                    # ── Stats (left) + vertical temp range bar (right) ────
                    with a.div(id="day-body-lower"):
                        with a.div(id="day-body-stats"):
                            self._render_stats(a, forecast)
                        if temp_min is not None:
                            _span = _scale_max - _scale_min
                            _top_pct    = round((_scale_max - temp_max) / _span * 100, 1)
                            _bottom_pct = round((temp_min - _scale_min) / _span * 100, 1)
                            with a.div(id="day-temp-range"):
                                a.img(src="icon/thermometer.png", klass="temp-range-icon")
                                a.span(klass="temp-range-high", _t=f"{temp_max}{temp_unit}")
                                with a.div(klass="temp-bar-track-v"):
                                    a.div(
                                        klass="temp-bar-pill-v",
                                        style=f"top:{_top_pct}%;bottom:{_bottom_pct}%",
                                    )
                                a.span(klass="temp-range-low", _t=f"{temp_min}{temp_unit}")

                    # ── Alerts ────────────────────────────────────────────
                    if alerts:
                        with a.div(id="day-alerts"):
                            for alert_text in alerts:
                                with a.div(klass="alert-item"):
                                    a.span(klass="alert-icon", _t="\u26a0")
                                    a.span(klass="alert-text", _t=alert_text)


