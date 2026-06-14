import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests

from ..cache import DiskCache
from ..service import WeatherService
from ..registry import register

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_FORECAST_URL = "http://openaccess.pf.api.met.ie/metno-wdb2ts/locationforecast"
_USER_AGENT = "inkplate10-weather-cal/1.0"

log = logging.getLogger(__name__)


def _parse_dt(s: str) -> datetime:
    """Parse an ISO-8601 string from the API into a timezone-aware datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _feels_like(temp_c: float, humidity: float, wind_ms: float) -> float:
    """Estimate apparent temperature.

    Uses Wind Chill for cold/windy conditions and Heat Index for hot/humid
    ones; returns the actual temperature for moderate conditions.
    """
    wind_kmh = wind_ms * 3.6

    if temp_c <= 10 and wind_kmh >= 4.8:
        # Wind Chill (Environment Canada / WMO formula)
        wc = (
            13.12
            + 0.6215 * temp_c
            - 11.37 * (wind_kmh ** 0.16)
            + 0.3965 * temp_c * (wind_kmh ** 0.16)
        )
        return round(wc)

    if temp_c >= 27 and humidity >= 40:
        # Rothfusz Heat Index (°C version)
        T = temp_c
        R = humidity
        hi = (
            -8.78469475556
            + 1.61139411 * T
            + 2.3385248863 * R
            - 0.14611605 * T * R
            - 0.01230809461 * T * T
            - 0.01642482777 * R * R
            + 0.00221173 * T * T * R
            + 0.00072546 * T * R * R
            - 0.00000358 * T * T * R * R
        )
        return round(hi)

    return round(temp_c)


@register("meteireann")
class MetEireannService(WeatherService):
    def __init__(self, *, apikey=None, location=None, num_hours=6, metric=True):
        super().__init__(
            apikey=None,
            baseurl=_FORECAST_URL,
            service_name="meteireann",
            num_hours=num_hours,
            metric=metric,
        )
        self.cache = DiskCache(Path(__file__).parent / ".cache.json", "Met Éireann")
        if not location:
            raise ValueError("MetEireannService requires a location (e.g. 'Dublin')")
        self.lat, self.lon = self._get_coords(location)

    _FORECAST_KEYS = ("daily_summary", "hourly_forecast", "5day_forecast", "current_conditions")

    def invalidate_forecast_cache(self):
        self.cache.delete(*self._FORECAST_KEYS)
        log.debug("Met Éireann forecast cache invalidated")

    # ── Geocoding ────────────────────────────────────────────────────────────

    def _get_coords(self, location: str) -> tuple[float, float]:
        cached = self.cache.get("coords", ttl=None)
        if cached and cached.get("location") == location:
            log.debug("Met Éireann coords cache hit for %s", location)
            return cached["lat"], cached["lon"]

        res = requests.get(
            _NOMINATIM_URL,
            params={"q": location, "format": "json", "limit": 1},
            headers={"User-Agent": _USER_AGENT},
        )
        data = res.json()

        if not data:
            raise ValueError(f"Nominatim returned no results for location: {location!r}")

        lat = round(float(data[0]["lat"]), 4)
        lon = round(float(data[0]["lon"]), 4)

        self.cache.set("coords", {"location": location, "lat": lat, "lon": lon})

        log.debug("Resolved %r → lat=%s lon=%s", location, lat, lon)
        return lat, lon

    # ── XML fetch & parse ────────────────────────────────────────────────────

    def _fetch_xml(self) -> str:
        cached = self.cache.get("xml_raw")
        if cached is not None:
            return cached

        url = f"{self.baseurl}?lat={self.lat};long={self.lon}"
        res = requests.get(url, headers={"User-Agent": _USER_AGENT})
        res.raise_for_status()
        xml_text = res.text
        self.cache.set("xml_raw", xml_text)
        return xml_text

    def _parse_entries(self) -> tuple[dict, list]:
        """Return (instants, periods).

        instants: dict mapping UTC datetime → dict of instant parameters
                  (temperature_c, wind_ms, wind_deg, humidity)
        periods:  list of dicts with keys from_dt, to_dt, symbol, precip_mm
        """
        xml_text = self._fetch_xml()
        root = ET.fromstring(xml_text)
        product = root.find("product")
        if product is None:
            raise ValueError("Unexpected Met Éireann XML: <product> element missing")

        instants: dict[datetime, dict] = {}
        periods: list[dict] = []

        for time_el in product.findall("time"):
            from_str = time_el.get("from", "")
            to_str = time_el.get("to", "")
            from_dt = _parse_dt(from_str)
            to_dt = _parse_dt(to_str)
            loc = time_el.find("location")
            if loc is None:
                continue

            if from_dt == to_dt:
                # Instant entry
                temp_el = loc.find("temperature")
                wind_speed_el = loc.find("windSpeed")
                wind_dir_el = loc.find("windDirection")
                humidity_el = loc.find("humidity")

                instants[from_dt] = {
                    "temperature_c": float(temp_el.get("value", 0)) if temp_el is not None else None,
                    "wind_ms": float(wind_speed_el.get("mps", 0)) if wind_speed_el is not None else None,
                    "wind_deg": float(wind_dir_el.get("deg", 0)) if wind_dir_el is not None else None,
                    "humidity": float(humidity_el.get("value", 0)) if humidity_el is not None else None,
                }
            else:
                # Period entry (typically 1-hour windows)
                symbol_el = loc.find("symbol")
                precip_el = loc.find("precipitation")
                symbol_id = symbol_el.get("id", "") if symbol_el is not None else ""
                precip = float(precip_el.get("value", 0)) if precip_el is not None else 0.0
                periods.append({
                    "from_dt": from_dt,
                    "to_dt": to_dt,
                    "symbol": symbol_id,
                    "precip_mm": precip,
                })

        return instants, periods

    # ── Unit helpers ─────────────────────────────────────────────────────────

    def _temp(self, temp_c: float) -> int:
        if self.units == "imperial":
            return round(temp_c * 9 / 5 + 32)
        return round(temp_c)

    def _wind_speed(self, wind_ms: float) -> float:
        if self.units == "imperial":
            return round(wind_ms * 2.237, 1)
        return round(wind_ms * 3.6, 1)

    @property
    def _temp_unit(self) -> str:
        return "\N{DEGREE SIGN}F" if self.units == "imperial" else "\N{DEGREE SIGN}C"

    @property
    def _speed_unit(self) -> str:
        return "mph" if self.units == "imperial" else "kmh"

    # ── Symbol lookup ────────────────────────────────────────────────────────

    def _dominant_symbol(self, periods: list[dict], from_dt: datetime, to_dt: datetime) -> str:
        """Return the most common symbol code across periods in the given window."""
        window = [
            p["symbol"] for p in periods
            if p["from_dt"] >= from_dt and p["to_dt"] <= to_dt and p["symbol"]
        ]
        if not window:
            return ""
        # Most frequent symbol in the window
        return max(set(window), key=window.count)

    # ── Public interface ─────────────────────────────────────────────────────

    def get_current_conditions(self) -> dict:
        cached = self.cache.get("current_conditions")
        if cached is not None:
            return cached

        instants, _ = self._parse_entries()
        if not instants:
            raise ValueError("No instant entries in Met Éireann response")

        now_utc = datetime.now(tz=timezone.utc)
        # Nearest instant at or before now
        past = {dt: v for dt, v in instants.items() if dt <= now_utc}
        if not past:
            dt_key = min(instants.keys())
        else:
            dt_key = max(past.keys())

        entry = instants[dt_key]
        temp_c = entry["temperature_c"]
        wind_ms = entry["wind_ms"] or 0.0
        humidity = entry["humidity"] or 0.0

        result = {
            "icon": self.get_icon(  # best effort — no per-instant symbol
                self._dominant_symbol(
                    self._parse_entries()[1],
                    dt_key,
                    dt_key.replace(hour=dt_key.hour + 1) if dt_key.hour < 23 else dt_key,
                )
            ),
            "temperature": {
                "unit": self._temp_unit,
                "value": self._temp(temp_c),
                "feels_like": self._temp(
                    _feels_like(temp_c, humidity, wind_ms)
                    if self.units == "metric"
                    else _feels_like(temp_c, humidity, wind_ms)
                ),
            },
            "wind": {
                "unit": self._speed_unit,
                "value": self._wind_speed(wind_ms),
                "direction_degrees": round(entry["wind_deg"] or 0),
            },
            "humidity": round(humidity),
            "uv_index": None,
            "weather_text": None,
        }
        self.cache.set("current_conditions", result)
        return result

    def get_daily_summary(self) -> dict:
        cached = self.cache.get("daily_summary")
        if cached is not None:
            return cached

        instants, periods = self._parse_entries()
        now_utc = datetime.now(tz=timezone.utc)
        today = now_utc.date()

        today_instants = {
            dt: v for dt, v in instants.items()
            if dt.date() == today
        }
        if not today_instants:
            raise ValueError("No forecast entries for today in Met Éireann response")

        temps = [v["temperature_c"] for v in today_instants.values() if v["temperature_c"] is not None]
        winds = [v for v in today_instants.values() if v["wind_ms"] is not None]

        # Representative entry: closest to noon
        noon_utc = now_utc.replace(hour=12, minute=0, second=0, microsecond=0)
        noon_entry = min(today_instants.items(), key=lambda kv: abs((kv[0] - noon_utc).total_seconds()))
        noon_wind = noon_entry[1]

        from_dt = min(today_instants.keys())
        to_dt = max(today_instants.keys())
        symbol = self._dominant_symbol(periods, from_dt, to_dt)

        # Rain probability: fraction of today's 1h periods that have precipitation
        today_periods = [
            p for p in periods
            if p["from_dt"].date() == today
        ]
        if today_periods:
            rainy = sum(1 for p in today_periods if p["precip_mm"] > 0.1)
            rain_prob = round(rainy / len(today_periods) * 100)
        else:
            rain_prob = 0

        # Feels-like: use noon entry
        noon_temp_c = noon_entry[1]["temperature_c"] or 0
        noon_humid = noon_entry[1]["humidity"] or 0
        noon_wind_ms = noon_entry[1]["wind_ms"] or 0

        result = {
            "icon": self.get_icon(symbol),
            "temperature": {
                "unit": self._temp_unit,
                "min": self._temp(min(temps)),
                "max": self._temp(max(temps)),
                "feels_like": self._temp(_feels_like(noon_temp_c, noon_humid, noon_wind_ms)),
            },
            "wind": {
                "unit": self._speed_unit,
                "value": self._wind_speed(noon_wind["wind_ms"] or 0),
                "direction_degrees": round(noon_wind["wind_deg"] or 0),
            },
            "humidity": round(sum(v["humidity"] or 0 for v in today_instants.values()) / len(today_instants)),
            "rain_probability": rain_prob,
            "pollen": None,
        }
        self.cache.set("daily_summary", result)
        return result

    def get_hourly_forecast(self) -> list:
        cached = self.cache.get("hourly_forecast")
        if cached is not None:
            return cached

        instants, periods = self._parse_entries()
        now_utc = datetime.now(tz=timezone.utc)

        # Build a symbol lookup: period from_dt → symbol
        symbol_by_hour: dict[datetime, str] = {p["from_dt"]: p["symbol"] for p in periods}

        # Only future instants, in order
        future = sorted(
            ((dt, v) for dt, v in instants.items() if dt >= now_utc),
            key=lambda kv: kv[0],
        )[: self.num_hours]

        results = []
        for dt_key, entry in future:
            temp_c = entry["temperature_c"] or 0
            wind_ms = entry["wind_ms"] or 0.0
            humidity = entry["humidity"] or 0.0
            symbol = symbol_by_hour.get(dt_key, "")

            results.append({
                "dt": dt_key.astimezone(tz=None).replace(tzinfo=None),
                "icon": self.get_icon(symbol),
                "temperature": {
                    "unit": self._temp_unit,
                    "value": self._temp(temp_c),
                },
                "wind": {
                    "unit": self._speed_unit,
                    "value": self._wind_speed(wind_ms),
                    "direction_degrees": round(entry["wind_deg"] or 0),
                },
                "humidity": round(humidity),
                "rain_probability": 0,  # individual hour probability not available
            })

        self.cache.set("hourly_forecast", results)
        return results

    def get_5day_forecast(self) -> list:
        cached = self.cache.get("5day_forecast")
        if cached is not None:
            return cached

        instants, periods = self._parse_entries()
        now_utc = datetime.now(tz=timezone.utc)

        # Group instants by date
        by_date: dict = defaultdict(dict)
        for dt_key, v in instants.items():
            if dt_key >= now_utc:
                by_date[dt_key.date()][dt_key] = v

        dates = sorted(by_date.keys())[:5]
        results = []

        for day in dates:
            day_instants = by_date[day]
            temps = [v["temperature_c"] for v in day_instants.values() if v["temperature_c"] is not None]
            if not temps:
                continue

            # Noon representative
            noon_utc = datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=timezone.utc)
            noon_entry = min(day_instants.items(), key=lambda kv: abs((kv[0] - noon_utc).total_seconds()))
            noon_data = noon_entry[1]

            from_dt = min(day_instants.keys())
            to_dt = max(day_instants.keys())
            symbol = self._dominant_symbol(periods, from_dt, to_dt)

            results.append({
                "dt": datetime(day.year, day.month, day.day),
                "icon": self.get_icon(symbol),
                "temperature": {
                    "unit": self._temp_unit,
                    "min": self._temp(min(temps)),
                    "max": self._temp(max(temps)),
                },
                "wind": {
                    "unit": self._speed_unit,
                    "value": self._wind_speed(noon_data["wind_ms"] or 0),
                    "direction_degrees": round(noon_data["wind_deg"] or 0),
                },
                "rain_probability": 0,
                "uv_index": None,
                "pollen": None,
                "sunrise": None,
                "sunset": None,
                "hours_of_sun": None,
                "hours_of_rain": None,
                "day_phrase": None,
                "night_phrase": None,
            })

        self.cache.set("5day_forecast", results)
        return results
