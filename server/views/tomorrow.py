from .simplified import SimplifiedPage, _uv_category, _wind_direction, _fmt_hours


class TomorrowPage(SimplifiedPage):
    def __init__(self, width, height):
        super().__init__(width, height)
        self.name = "tomorrow"

    def template(self, **kwargs):
        super().template(
            map_url=kwargs["map_url"],
            forecast=kwargs["tomorrow_forecast"],
        )

    def _css_links(self, a):
        super()._css_links(a)
        a.link(rel="stylesheet", href="tomorrow.css")

    def _render_stats(self, a, forecast):
        rain_prob = forecast["rain_probability"]
        uv_idx = forecast.get("uv_index")
        wind_val = forecast["wind"]["value"]
        wind_unit = forecast["wind"]["unit"]
        wind_deg = forecast["wind"]["direction_degrees"]
        hours_of_sun = forecast.get("hours_of_sun")
        hours_of_rain = forecast.get("hours_of_rain")

        wind_unit_display = "kph" if wind_unit == "kmh" else "mph"

        with a.div(id="tomorrow-stats"):

            # Rain — row 1 (no indent)
            with a.div(klass="stat-row stat-rain"):
                a.img(src="icon/raindrops.png", klass="stat-icon")
                with a.div(klass="stat-text"):
                    rain_hrs = _fmt_hours(hours_of_rain)
                    if rain_hrs and hours_of_rain > 0:
                        a.span(
                            klass="stat-primary",
                            _t=f"{rain_hrs} of rain",
                        )
                        a.span(
                            klass="stat-secondary",
                            _t=f"{rain_prob}% chance of rain",
                        )
                    else:
                        a.span(
                            klass="stat-primary",
                            _t=f"{rain_prob}% chance of rain",
                        )

            # UV — row 2 (indented)
            if uv_idx is not None:
                with a.div(klass="stat-row stat-uv"):
                    a.img(src="icon/sun.png", klass="stat-icon")
                    with a.div(klass="stat-text"):
                        sun_hrs = _fmt_hours(hours_of_sun)
                        if sun_hrs is not None:
                            a.span(
                                klass="stat-primary",
                                _t=f"{sun_hrs} of sunshine",
                            )
                            a.span(
                                klass="stat-secondary",
                                _t=f"UV Index {uv_idx}",
                            )
                        else:
                            a.span(
                                klass="stat-primary",
                                _t=f"UV Index {uv_idx}",
                            )
                            a.span(
                                klass="stat-secondary",
                                _t=_uv_category(uv_idx),
                            )

            # Wind — row 3 (most indented)
            with a.div(klass="stat-row stat-wind"):
                a.img(
                    src="icon/wind.png",
                    klass="stat-icon wind",
                    style=f"transform: rotate({(wind_deg + 180) % 360}deg);",
                )
                with a.div(klass="stat-text"):
                    a.span(
                        klass="stat-primary",
                        _t=f"{round(wind_val)} {wind_unit_display}",
                    )
                    a.span(
                        klass="stat-secondary",
                        _t=_wind_direction(wind_deg),
                    )
