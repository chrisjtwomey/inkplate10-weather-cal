import json
import logging
import os
import time
import requests
from datetime import datetime
from utils import even_select
from ..service import WeatherService

_CACHE_TTL = 3300  # 55 minutes — public API responses

log = logging.getLogger(__name__)


def _json_default(obj):
    if isinstance(obj, datetime):
        return {"__dt__": obj.isoformat()}
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _json_hook(d):
    if "__dt__" in d:
        return datetime.fromisoformat(d["__dt__"])
    return d


class AccuweatherService(WeatherService):
    def __init__(self, apikey, location, num_hours=6, metric=True):
        super().__init__(
            apikey,
            "http://dataservice.accuweather.com",
            "accuweather",
            num_hours,
            metric,
        )
        self._cache_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), ".cache.json"
        )
        self.location_key = self._get_location_key(location)

    # ── Cache helpers ────────────────────────────────────────────────────────

    def _load_cache(self):
        try:
            with open(self._cache_path) as f:
                return json.load(f, object_hook=_json_hook)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_cache(self, cache):
        try:
            with open(self._cache_path, "w") as f:
                json.dump(cache, f, default=_json_default)
        except OSError as exc:
            log.warning("Could not write AccuWeather cache: %s", exc)

    def _get_cached(self, key, ttl=_CACHE_TTL):
        entry = self._load_cache().get(key)
        if entry and time.time() - entry["ts"] < ttl:
            log.debug("AccuWeather cache hit: %s", key)
            return entry["data"]
        return None

    def _set_cached(self, key, data):
        # Reload before writing to avoid overwriting concurrent entries.
        cache = self._load_cache()
        cache[key] = {"ts": time.time(), "data": data}
        self._save_cache(cache)

    _FORECAST_KEYS = ("daily_summary", "hourly_forecast", "5day_forecast", "current_conditions")

    def invalidate_forecast_cache(self):
        """Remove forecast entries from cache; location_key is preserved."""
        cache = self._load_cache()
        for key in self._FORECAST_KEYS:
            cache.pop(key, None)
        self._save_cache(cache)
        log.debug("AccuWeather forecast cache invalidated")

    def get_daily_summary(self):
        cached = self._get_cached("daily_summary")
        if cached is not None:
            return cached

        is_metric = self.units == "metric"
        path = f"{self.baseurl}/forecasts/v1/daily/1day/{self.location_key}?apikey={self.apikey}&metric={is_metric}&details=true"
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        if len(data["DailyForecasts"]) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        current_conditions = self._get_current_conditions()

        data = data["DailyForecasts"][0]
        pollen = [
            {
                "name": ap["Name"],
                "category": ap.get("Category", "Unknown"),
                "category_value": ap.get("CategoryValue", 0),
            }
            for ap in data.get("AirAndPollen", [])
            if ap.get("Name") in ("Grass", "Tree", "Ragweed", "Mold")
        ]
        forecast = {
            "icon": self.get_icon(data["Day"]["Icon"]),
            "temperature": {
                "unit": "\N{DEGREE SIGN}C"
                if self.units == "metric"
                else "\N{DEGREE SIGN}F",
                "min": round(data["Temperature"]["Minimum"]["Value"]),
                "max": round(data["Temperature"]["Maximum"]["Value"]),
                "feels_like": round(data["RealFeelTemperature"]["Maximum"]["Value"]),
            },
            "wind": current_conditions["wind"],
            "humidity": current_conditions["humidity"],
            "rain_probability": round(data["Day"].get("PrecipitationProbability", 0)),
            "pollen": pollen or None,
        }

        self._set_cached("daily_summary", forecast)
        return forecast

    def get_hourly_forecast(self):
        cached = self._get_cached("hourly_forecast")
        if cached is not None:
            return cached

        is_metric = self.units == "metric"
        path = f"{self.baseurl}/forecasts/v1/hourly/12hour/{self.location_key}?apikey={self.apikey}&metric={is_metric}&details=true"
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        if self.units == "metric":
            temp_units = "\N{DEGREE SIGN}C"
            speed_units = "kmh"
        else:
            temp_units = "\N{DEGREE SIGN}F"
            speed_units = "mph"

        forecasts = []
        for entry in even_select(self.num_hours, data):
            forecast = {
                "dt": datetime.fromtimestamp(entry["EpochDateTime"]),
                "icon": self.get_icon(entry["WeatherIcon"]),
                "temperature": {
                    "unit": temp_units,
                    "value": round(entry["RealFeelTemperature"]["Value"]),
                },
                "wind": {
                    "unit": speed_units,
                    "value": entry["Wind"]["Speed"]["Value"],
                    "direction_degrees": entry["Wind"].get("Direction", {}).get("Degrees", 0),
                },
                "humidity": entry["RelativeHumidity"],
                "rain_probability": round(entry["RainProbability"]),
            }

            forecasts.append(forecast)

        self._set_cached("hourly_forecast", forecasts)
        return forecasts

    def get_5day_forecast(self):
        cached = self._get_cached("5day_forecast")
        if cached is not None:
            return cached

        is_metric = self.units == "metric"
        path = (
            f"{self.baseurl}/forecasts/v1/daily/5day/{self.location_key}"
            f"?apikey={self.apikey}&metric={is_metric}&details=true"
        )
        res = requests.get(path)

        if res.status_code == 403:
            raise PermissionError(
                "AccuWeather 5-day endpoint returned 403 — "
                "this endpoint may require a plan upgrade"
            )

        data = res.json()
        if not data.get("DailyForecasts"):
            raise ValueError("Unexpected response from weather api: {}".format(data))

        temp_unit = (
            "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        )
        speed_unit = "kmh" if self.units == "metric" else "mph"

        forecasts = []
        for entry in data["DailyForecasts"]:
            # UV index and pollen from AirAndPollen list
            uv_index = None
            pollen = []
            for ap in entry.get("AirAndPollen", []):
                name = ap.get("Name")
                if name == "UVIndex":
                    uv_index = ap.get("Value")
                elif name in ("Grass", "Tree", "Ragweed", "Mold"):
                    pollen.append({
                        "name": name,
                        "category": ap.get("Category", "Unknown"),
                        "category_value": ap.get("CategoryValue", 0),
                    })

            # Sunrise / sunset as "HH:MM" strings
            sunrise = None
            sunset = None
            sun = entry.get("Sun", {})
            if sun.get("Rise"):
                try:
                    sunrise = datetime.fromisoformat(sun["Rise"]).strftime("%H:%M")
                except (ValueError, TypeError):
                    pass
            if sun.get("Set"):
                try:
                    sunset = datetime.fromisoformat(sun["Set"]).strftime("%H:%M")
                except (ValueError, TypeError):
                    pass

            forecasts.append({
                "dt": datetime.fromtimestamp(entry["EpochDate"]),
                "icon": self.get_icon(entry["Day"]["Icon"]),
                "temperature": {
                    "unit": temp_unit,
                    "min": round(entry["RealFeelTemperature"]["Minimum"]["Value"]),
                    "max": round(entry["RealFeelTemperature"]["Maximum"]["Value"]),
                },
                "wind": {
                    "unit": speed_unit,
                    "value": entry["Day"]["Wind"]["Speed"]["Value"],
                    "direction_degrees": entry["Day"]["Wind"].get("Direction", {}).get("Degrees", 0),
                },
                "rain_probability": round(entry["Day"].get("PrecipitationProbability", 0)),
                "uv_index": uv_index,
                "pollen": pollen or None,
                "sunrise": sunrise,
                "sunset": sunset,
                "hours_of_sun": entry.get("HoursOfSun"),
                "hours_of_rain": entry.get("Day", {}).get("HoursOfRain"),
                "day_phrase": entry.get("Day", {}).get("LongPhrase"),
                "night_phrase": entry.get("Night", {}).get("ShortPhrase"),
            })

        self._set_cached("5day_forecast", forecasts)
        return forecasts

    def _get_current_conditions(self):
        cached = self._get_cached("current_conditions")
        if cached is not None:
            return cached

        path = f"{self.baseurl}/currentconditions/v1/{self.location_key}?apikey={self.apikey}&details=true"
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        if self.units == "metric":
            temp_units = "\N{DEGREE SIGN}C"
            speed_units = "kmh"
            units_key = "Metric"
        else:
            temp_units = "\N{DEGREE SIGN}F"
            speed_units = "mph"
            units_key = "Imperial"

        data = data[0]
        conditions = {
            "icon": self.get_icon(data["WeatherIcon"]),
            "temperature": {
                "unit": temp_units,
                "value": round(data["Temperature"][units_key]["Value"]),
                "feels_like": round(data["RealFeelTemperature"][units_key]["Value"]),
            },
            "wind": {
                "unit": speed_units,
                "value": data["Wind"]["Speed"][units_key]["Value"],
                "direction_degrees": data["Wind"].get("Direction", {}).get("Degrees", 0),
            },
            "humidity": data["RelativeHumidity"],
            "uv_index": data.get("UVIndex"),
            "weather_text": data.get("WeatherText"),
        }

        self._set_cached("current_conditions", conditions)
        return conditions

    def get_current_conditions(self):
        return self._get_current_conditions()

    def _get_location_key(self, location):
        # Cached indefinitely — only re-fetch if the location string has changed.
        entry = self._load_cache().get("location_key")
        if entry and entry.get("location") == location:
            log.debug("AccuWeather cache hit: location_key")
            return entry["data"]

        path = (
            f"{self.baseurl}/locations/v1/search?apikey={self.apikey}&q={location}"
        )
        res = requests.get(path)
        data = res.json()

        if len(data) == 0:
            raise ValueError("Unexpected response from weather api: {}".format(data))
        location_key = data[0]["Key"]

        cache = self._load_cache()
        cache["location_key"] = {"ts": time.time(), "location": location, "data": location_key}
        self._save_cache(cache)
        return location_key
