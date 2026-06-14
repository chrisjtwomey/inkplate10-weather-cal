import logging
from datetime import datetime, date
from pathlib import Path

import requests

from ..cache import DiskCache
from ..service import WeatherService
from ..registry import register

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

log = logging.getLogger(__name__)


@register("openmeteo")
class OpenMeteoService(WeatherService):
    def __init__(self, *, apikey=None, location=None, num_hours=6, metric=True):
        super().__init__(
            apikey=None,
            baseurl=_FORECAST_URL,
            service_name="openmeteo",
            num_hours=num_hours,
            metric=metric,
        )
        self.cache = DiskCache(Path(__file__).parent / ".cache.json", "Open-Meteo")
        if not location:
            raise ValueError("OpenMeteoService requires a location (e.g. 'Dublin')")
        self.lat, self.lon = self._get_coords(location)

    _FORECAST_KEYS = ("forecast", "current_conditions", "daily_summary", "hourly_forecast", "5day_forecast")

    def invalidate_forecast_cache(self) -> None:
        self.cache.delete(*self._FORECAST_KEYS)
        log.debug("Open-Meteo forecast cache invalidated")

    # ── Geocoding ────────────────────────────────────────────────────────────

    def _get_coords(self, location: str) -> tuple[float, float]:
        cached = self.cache.get("coords", ttl=None)
        if cached and cached.get("location") == location:
            log.debug("Open-Meteo coords cache hit for %s", location)
            return cached["lat"], cached["lon"]

        res = requests.get(
            _GEOCODING_URL,
            params={"name": location, "count": 1, "format": "json"},
        )
        data = res.json()
        results = data.get("results")

        if not results:
            raise ValueError(
                f"Open-Meteo geocoding returned no results for location: {location!r}"
            )

        lat = round(float(results[0]["latitude"]), 4)
        lon = round(float(results[0]["longitude"]), 4)

        self.cache.set("coords", {"location": location, "lat": lat, "lon": lon})

        log.debug("Resolved %r → lat=%s lon=%s", location, lat, lon)
        return lat, lon

    # ── Forecast fetch ───────────────────────────────────────────────────────

    @property
    def _temp_unit_param(self) -> str:
        return "fahrenheit" if self.units == "imperial" else "celsius"

    @property
    def _wind_unit_param(self) -> str:
        return "mph" if self.units == "imperial" else "kmh"

    @property
    def _temp_unit(self) -> str:
        return "\N{DEGREE SIGN}F" if self.units == "imperial" else "\N{DEGREE SIGN}C"

    @property
    def _speed_unit(self) -> str:
        return "mph" if self.units == "imperial" else "kmh"

    def _fetch_forecast(self) -> dict:
        """Fetch current + hourly + daily in a single API call, cached ~55 min."""
        cached = self.cache.get("forecast")
        if cached is not None:
            return cached

        res = requests.get(
            self.baseurl,
            params={
                "latitude": self.lat,
                "longitude": self.lon,
                "current": ",".join([
                    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
                    "wind_speed_10m", "wind_direction_10m", "weather_code", "is_day",
                ]),
                "hourly": ",".join([
                    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
                    "wind_speed_10m", "wind_direction_10m",
                    "precipitation_probability", "weather_code", "is_day",
                ]),
                "daily": ",".join([
                    "temperature_2m_max", "temperature_2m_min", "apparent_temperature_max",
                    "precipitation_probability_max", "weather_code",
                    "wind_speed_10m_max", "wind_direction_10m_dominant",
                    "uv_index_max", "sunrise", "sunset", "sunshine_duration",
                ]),
                "temperature_unit": self._temp_unit_param,
                "wind_speed_unit": self._wind_unit_param,
                "forecast_days": 7,
                "timezone": "auto",
            },
        )
        res.raise_for_status()
        data = res.json()
        self.cache.set("forecast", data)
        return data

    def _icon_key(self, wmo_code: int, is_day: int) -> str:
        return f"{wmo_code}_{'day' if is_day else 'night'}"

    # ── Public interface ─────────────────────────────────────────────────────

    def get_current_conditions(self) -> dict:
        cached = self.cache.get("current_conditions")
        if cached is not None:
            return cached

        data = self._fetch_forecast()
        current = data["current"]

        result: dict = {
            "icon": self.get_icon(self._icon_key(current["weather_code"], current["is_day"])),
            "temperature": {
                "unit": self._temp_unit,
                "value": round(current["temperature_2m"]),
                "feels_like": round(current["apparent_temperature"]),
            },
            "wind": {
                "unit": self._speed_unit,
                "value": round(current["wind_speed_10m"], 1),
                "direction_degrees": round(current["wind_direction_10m"]),
            },
            "humidity": round(current["relative_humidity_2m"]),
            "uv_index": None,
            "weather_text": None,
        }
        self.cache.set("current_conditions", result)
        return result

    def get_daily_summary(self) -> dict:
        cached = self.cache.get("daily_summary")
        if cached is not None:
            return cached

        data = self._fetch_forecast()
        daily = data["daily"]

        # Index 0 is always today (daily array starts from the current day)
        result: dict = {
            "icon": self.get_icon(self._icon_key(daily["weather_code"][0], 1)),
            "temperature": {
                "unit": self._temp_unit,
                "min": round(daily["temperature_2m_min"][0]),
                "max": round(daily["temperature_2m_max"][0]),
                "feels_like": round(daily["apparent_temperature_max"][0]),
            },
            "wind": {
                "unit": self._speed_unit,
                "value": round(daily["wind_speed_10m_max"][0], 1),
                "direction_degrees": round(daily["wind_direction_10m_dominant"][0]),
            },
            "humidity": None,
            "rain_probability": round(daily["precipitation_probability_max"][0] or 0),
            "pollen": None,
        }
        self.cache.set("daily_summary", result)
        return result

    def get_hourly_forecast(self) -> list:
        cached = self.cache.get("hourly_forecast")
        if cached is not None:
            return cached

        data = self._fetch_forecast()
        hourly = data["hourly"]

        # Use the API's own current time as the reference so tests are deterministic.
        current_time = datetime.fromisoformat(data["current"]["time"])
        times = [datetime.fromisoformat(t) for t in hourly["time"]]
        indices = [i for i, t in enumerate(times) if t >= current_time][: self.num_hours]

        results = []
        for i in indices:
            results.append({
                "dt": times[i],
                "icon": self.get_icon(
                    self._icon_key(hourly["weather_code"][i], hourly["is_day"][i])
                ),
                "temperature": {
                    "unit": self._temp_unit,
                    "value": round(hourly["temperature_2m"][i]),
                },
                "wind": {
                    "unit": self._speed_unit,
                    "value": round(hourly["wind_speed_10m"][i], 1),
                    "direction_degrees": round(hourly["wind_direction_10m"][i]),
                },
                "humidity": round(hourly["relative_humidity_2m"][i]),
                "rain_probability": round(hourly["precipitation_probability"][i] or 0),
            })

        self.cache.set("hourly_forecast", results)
        return results

    def get_5day_forecast(self) -> list:
        cached = self.cache.get("5day_forecast")
        if cached is not None:
            return cached

        data = self._fetch_forecast()
        daily = data["daily"]

        results = []
        for i, day_str in enumerate(daily["time"][:5]):
            day = date.fromisoformat(day_str)

            sunrise_raw = daily["sunrise"][i]
            sunset_raw = daily["sunset"][i]
            sunrise_str = datetime.fromisoformat(sunrise_raw).strftime("%H:%M") if sunrise_raw else None
            sunset_str = datetime.fromisoformat(sunset_raw).strftime("%H:%M") if sunset_raw else None

            sunshine_seconds = daily.get("sunshine_duration", [None] * 8)[i]
            hours_of_sun = round(sunshine_seconds / 3600, 1) if sunshine_seconds is not None else None

            uv_raw = daily["uv_index_max"][i]

            results.append({
                "dt": datetime(day.year, day.month, day.day),
                "icon": self.get_icon(self._icon_key(daily["weather_code"][i], 1)),
                "temperature": {
                    "unit": self._temp_unit,
                    "min": round(daily["temperature_2m_min"][i]),
                    "max": round(daily["temperature_2m_max"][i]),
                },
                "wind": {
                    "unit": self._speed_unit,
                    "value": round(daily["wind_speed_10m_max"][i], 1),
                    "direction_degrees": round(daily["wind_direction_10m_dominant"][i]),
                },
                "rain_probability": round(daily["precipitation_probability_max"][i] or 0),
                "uv_index": round(uv_raw) if uv_raw is not None else None,
                "pollen": None,
                "sunrise": sunrise_str,
                "sunset": sunset_str,
                "hours_of_sun": hours_of_sun,
                "hours_of_rain": None,
                "day_phrase": None,
                "night_phrase": None,
            })

        self.cache.set("5day_forecast", results)
        return results
