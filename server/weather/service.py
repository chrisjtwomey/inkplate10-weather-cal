import os
import json
from abc import abstractmethod

from epd_server.source import DataSource


class WeatherService(DataSource):
    """A weather provider, exposed to pages as four named datasets.

    Subclasses implement the four ``get_*`` methods. ``datasets()`` maps them
    to the names the views declare in ``Page.requires``:

        current_conditions, daily_summary, hourly_forecasts, daily_forecasts

    Nothing is fetched until a page that needs it is regenerated.
    """

    def __init__(
        self, apikey, baseurl, service_name, num_hours=6, metric=True
    ):
        self.baseurl = baseurl
        self.service_name = service_name
        self.apikey = apikey
        self.units = "metric" if metric else "imperial"
        self.num_hours = num_hours

    def get_icon(self, icon_key):
        icon_key = str(icon_key)

        cwd = os.path.dirname(os.path.realpath(__file__))
        mapfile_path = os.path.join(
            cwd, "..", f"weather/{self.service_name}/icon-map.json"
        )
        icon_map = None
        with open(mapfile_path) as f:
            icon_map = json.load(f)

        if icon_key not in icon_map:
            return ""

        return f"icon/{icon_map[icon_key]}"

    def invalidate_forecast_cache(self):
        """No-op for services that don't cache."""
        pass

    # ── DataSource ────────────────────────────────────────────────────────

    def datasets(self):
        return {
            "current_conditions": self.get_current_conditions,
            "daily_summary": self.get_daily_summary,
            "hourly_forecasts": self.get_hourly_forecast,
            "daily_forecasts": self.get_5day_forecast,
        }

    def invalidate(self):
        self.invalidate_forecast_cache()

    @abstractmethod
    def get_current_conditions(self) -> dict:
        """Return a dict of current weather conditions.

        Expected keys: icon, temperature (unit, value, feels_like),
        wind (unit, value, direction_degrees), humidity, uv_index, weather_text.
        """

    @abstractmethod
    def get_5day_forecast(self) -> list:
        """Return a list of dicts, one per day, for the next 5 days.

        Expected keys per entry: dt, icon, temperature (unit, min, max),
        wind, rain_probability, uv_index, pollen, sunrise, sunset,
        hours_of_sun, hours_of_rain, day_phrase, night_phrase.
        """

    @abstractmethod
    def get_daily_summary(self) -> dict:
        """Return a dict summarising today's forecast.

        Expected keys: icon, temperature (unit, min, max, feels_like),
        wind, humidity, rain_probability, pollen.
        """

    @abstractmethod
    def get_hourly_forecast(self) -> list:
        """Return a list of dicts for the next ``num_hours`` hours.

        Expected keys per entry: dt, icon, temperature (unit, value),
        wind (unit, value, direction_degrees), humidity, rain_probability.
        """
