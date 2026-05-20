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

    def _render_stats(self, a, forecast):
        pass  # subclasses override to insert a stats section

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

            with a.body():
                # ── Map ──────────────────────────────────────────────────
                with a.div(id="day-map-wrapper"):
                    with a.div(id="map-container"):
                        a.img(src=map_url, id="map")

                # ── Content section ───────────────────────────────────────
                with a.div(id="day-body", klass="bg-container"):

                    # ── Hero: icon → date → temperature → range → phrase ──
                    with a.div(id="day-hero"):
                        a.img(src=forecast["icon"], id="day-icon")
                        a.p(id="day-date", _t=date_str)
                        a.p(id="day-temp-main", _t=f"{temp_max}{temp_unit}")
                        if temp_min is not None:
                            a.p(
                                id="day-temp-range",
                                _t=f"{temp_min}\u2013{temp_max}{temp_unit}",
                            )
                        if day_phrase:
                            a.p(id="day-phrase", _t=day_phrase)

                    # ── Hook for subclass stats sections ──────────────────
                    self._render_stats(a, forecast)

                    # ── Alerts ────────────────────────────────────────────
                    if alerts:
                        with a.div(id="day-alerts"):
                            for alert_text in alerts:
                                with a.div(klass="alert-item"):
                                    a.span(klass="alert-icon", _t="\u26a0")
                                    a.span(klass="alert-text", _t=alert_text)
