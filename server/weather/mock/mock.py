import random
import datetime as dt
from ..service import WeatherService
from ..registry import register


# Icons available in server/views/html/icon/
_DAY_ICONS = [
    "icon/day/clear.png",
    "icon/day/partly-clear.png",
    "icon/day/partly-clear-showers.png",
    "icon/day/partly-clear-windy.png",
    "icon/cloudy.png",
    "icon/cloudy-showers.png",
    "icon/rainy.png",
    "icon/rainy-windy.png",
    "icon/foggy.png",
]

_NIGHT_ICONS = [
    "icon/night/clear.png",
    "icon/night/partly-clear.png",
    "icon/cloudy.png",
    "icon/rainy.png",
]

_DAY_PHRASES = [
    "Partly sunny with some afternoon clouds",
    "Mostly sunny and pleasant",
    "Cloudy with periods of rain",
    "Sunny intervals, turning windy later",
    "A mix of sun and cloud",
    "Overcast with light showers throughout the day",
]

_NIGHT_PHRASES = [
    "Clear overnight",
    "Mostly cloudy",
    "Scattered showers possible",
    "Clearing up later in the night",
    "Remaining overcast",
]


_POLLEN_CATEGORIES = [
    ("Low", 1),
    ("Moderate", 2),
    ("High", 3),
    ("Very High", 4),
]


@register("mock")
class MockWeatherService(WeatherService):
    def __init__(self, *, apikey=None, location=None, num_hours=6, metric=True):
        super().__init__(
            apikey=None,
            baseurl=None,
            service_name="mock",
            num_hours=num_hours,
            metric=metric,
        )
        self._seed = random.randint(0, 9999)

    def get_daily_summary(self):
        rng = random.Random(self._seed)
        temp_unit = "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        temp_range = (-5, 35) if self.units == "metric" else (23, 95)
        pollen = [
            {"name": name, "category": cat, "category_value": val}
            for name, (cat, val) in zip(
                ("Grass", "Tree", "Ragweed"),
                [rng.choice(_POLLEN_CATEGORIES) for _ in range(3)],
            )
        ]
        return {
            "icon": rng.choice(_DAY_ICONS),
            "temperature": {
                "unit": temp_unit,
                "min": rng.randint(temp_range[0], temp_range[1] - 5),
                "max": rng.randint(temp_range[0] + 5, temp_range[1]),
                "value": rng.randint(temp_range[0] + 2, temp_range[1] - 2),
                "feels_like": rng.randint(temp_range[0], temp_range[1] - 3),
            },
            "wind": {
                "unit": "kmh" if self.units == "metric" else "mph",
                "value": rng.randint(0, 80),
            },
            "humidity": rng.randint(30, 100),
            "rain_probability": rng.randint(0, 100),
            "pollen": pollen,
        }

    def get_hourly_forecast(self):
        rng = random.Random(self._seed + 1)
        now = dt.datetime.now().replace(minute=0, second=0, microsecond=0)
        temp_unit = "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        speed_unit = "kmh" if self.units == "metric" else "mph"
        temp_range = (-5, 35) if self.units == "metric" else (23, 95)

        forecasts = []
        for i in range(self.num_hours):
            hour_dt = now + dt.timedelta(hours=i * 2)
            is_night = hour_dt.hour < 6 or hour_dt.hour >= 20
            icons = _NIGHT_ICONS if is_night else _DAY_ICONS
            forecasts.append({
                "dt": hour_dt,
                "icon": rng.choice(icons),
                "temperature": {
                    "unit": temp_unit,
                    "value": rng.randint(temp_range[0], temp_range[1]),
                },
                "wind": {
                    "unit": speed_unit,
                    "value": rng.randint(0, 80),
                    "direction_degrees": rng.randint(0, 359),
                },
                "humidity": rng.randint(30, 100),
                "rain_probability": rng.randint(0, 100),
            })

        return forecasts

    def get_5day_forecast(self):
        rng = random.Random(self._seed + 2)
        today = dt.datetime.now().date()
        temp_unit = "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        speed_unit = "kmh" if self.units == "metric" else "mph"
        temp_range = (-5, 35) if self.units == "metric" else (23, 95)

        forecasts = []
        for i in range(5):
            day = today + dt.timedelta(days=i)
            day_dt = dt.datetime.combine(day, dt.time(0, 0))
            temp_min = rng.randint(temp_range[0], temp_range[1] - 5)
            temp_max = rng.randint(temp_min + 1, temp_range[1])
            sunrise_h = rng.randint(6, 7)
            sunrise_m = rng.randint(0, 59)
            sunset_h = rng.randint(20, 21)
            sunset_m = rng.randint(0, 59)
            pollen = [
                {"name": name, "category": cat, "category_value": val}
                for name, (cat, val) in zip(
                    ("Grass", "Tree", "Ragweed"),
                    [rng.choice(_POLLEN_CATEGORIES) for _ in range(3)],
                )
            ]

            forecasts.append({
                "dt": day_dt,
                "icon": rng.choice(_DAY_ICONS),
                "temperature": {
                    "unit": temp_unit,
                    "min": temp_min,
                    "max": temp_max,
                },
                "wind": {
                    "unit": speed_unit,
                    "value": rng.randint(0, 80),
                    "direction_degrees": rng.randint(0, 359),
                },
                "rain_probability": rng.randint(0, 100),
                "uv_index": rng.randint(0, 11),
                "pollen": pollen,
                "sunrise": f"{sunrise_h:02d}:{sunrise_m:02d}",
                "sunset": f"{sunset_h:02d}:{sunset_m:02d}",
                "hours_of_sun": round(rng.uniform(0, 12), 1),
                "hours_of_rain": round(rng.uniform(0, 6), 1),
                "day_phrase": rng.choice(_DAY_PHRASES),
                "night_phrase": rng.choice(_NIGHT_PHRASES),
            })

        return forecasts

    def get_current_conditions(self):
        rng = random.Random(self._seed + 3)
        temp_unit = "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        temp_range = (-5, 35) if self.units == "metric" else (23, 95)
        speed_unit = "kmh" if self.units == "metric" else "mph"
        _weather_texts = [
            "Partly sunny", "Overcast", "Light rain", "Fog",
            "Cloudy", "Mostly sunny", "Showers",
        ]
        return {
            "icon": rng.choice(_DAY_ICONS),
            "temperature": {
                "unit": temp_unit,
                "value": rng.randint(temp_range[0], temp_range[1]),
                "feels_like": rng.randint(temp_range[0] - 3, temp_range[1]),
            },
            "wind": {
                "unit": speed_unit,
                "value": rng.randint(0, 80),
                "direction_degrees": rng.randint(0, 359),
            },
            "humidity": rng.randint(30, 100),
            "uv_index": rng.randint(0, 11),
            "weather_text": rng.choice(_weather_texts),
        }
