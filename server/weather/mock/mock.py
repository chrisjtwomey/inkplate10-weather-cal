import random
import datetime as dt


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


class MockWeatherService:
    def __init__(self, num_hours=6, metric=True):
        self.num_hours = num_hours
        self.units = "metric" if metric else "imperial"
        self._seed = random.randint(0, 9999)

    def get_daily_summary(self):
        rng = random.Random(self._seed)
        temp_unit = "\N{DEGREE SIGN}C" if self.units == "metric" else "\N{DEGREE SIGN}F"
        temp_range = (-5, 35) if self.units == "metric" else (23, 95)
        return {
            "icon": rng.choice(_DAY_ICONS),
            "temperature": {
                "unit": temp_unit,
                "min": rng.randint(temp_range[0], temp_range[1] - 5),
                "max": rng.randint(temp_range[0] + 5, temp_range[1]),
                "value": rng.randint(temp_range[0] + 2, temp_range[1] - 2),
            },
            "wind": {
                "unit": "kmh" if self.units == "metric" else "mph",
                "value": rng.randint(0, 80),
            },
            "humidity": rng.randint(30, 100),
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
