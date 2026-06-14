# Weather Service Plugin System

The weather layer is built around a **pluggable interface**: any weather source can be added without touching the rest of the server. This document explains the architecture and how to implement a custom service.

## Architecture

```
weather/
├── service.py      # WeatherService abstract base class (the interface)
├── registry.py     # Service registry and factory
├── accuweather/    # AccuWeather implementation
├── openweathermap/ # OpenWeatherMap implementation
├── meteireann/     # Met Éireann implementation (Ireland only)
├── openmeteo/      # Open-Meteo implementation
└── mock/           # Mock implementation (randomised data, no API key required)
```

### `WeatherService` (the interface)

`service.py` defines `WeatherService`, an abstract base class that every implementation must subclass. It declares four abstract methods — any class that doesn't implement all of them will raise a `TypeError` at instantiation time rather than failing silently at runtime.

| Method | Returns | Description |
|---|---|---|
| `get_current_conditions()` | `dict` | Current temperature, wind, humidity, UV index, and weather text. |
| `get_daily_summary()` | `dict` | Today's high/low, rain probability, pollen, wind, and humidity. |
| `get_hourly_forecast()` | `list[dict]` | Hourly entries for the next `num_hours` hours. |
| `get_5day_forecast()` | `list[dict]` | One entry per day for the next five days. |

The base class also provides:
- `get_icon(icon_key)` — Maps a provider-specific icon code to a local PNG path via the service's `icon-map.json`.
- `invalidate_forecast_cache()` — No-op by default; override if your service caches responses.

### `registry.py` (the factory)

The registry is a module-level dict that maps service names (as used in `config.yaml`) to their classes. Services register themselves using the `@register` decorator when their module is imported.

`create(name, *, apikey, location, num_hours, metric, **kwargs)` looks up the service class by name and instantiates it, forwarding only the kwargs that the constructor actually declares — so a service doesn't have to accept parameters it doesn't use.

## Built-in services

| `accuweather` | Backed by the [AccuWeather API](https://developer.accuweather.com/). Responses are cached server-side to minimize API calls between image regenerations. Requires: `weather.apikey`, `location`. |
| `openweathermap` | Backed by the [OpenWeatherMap API](https://openweathermap.org/api). No server-side caching; fetches fresh data on every generation. Requires: `weather.apikey`, `location`. |
| `meteireann` | Backed by [Met Éireann's forecast API](https://data.gov.ie/dataset/met-eireann-forecast-api) (Harmonie NWP model, ~2.5 km resolution). **Ireland only.** No API key required. Geocodes via Nominatim. Responses cached ~55 min. Requires: `location`. |
| `openmeteo` | Backed by the [Open-Meteo API](https://open-meteo.com/) (global coverage, WMO weather codes). **No API key required** for non-commercial use. Geocoding via Open-Meteo's own API. Responses cached ~55 min. Requires: `location`. |
| `mock` | Generates randomised but realistic weather data locally — no API key or network access needed. Useful for development, layout testing, and CI. Enable it by setting `weather.service: mock` in `config.yaml`. |

## Adding a custom weather service

1. **Create a directory** under `server/weather/` for your service, e.g. `server/weather/myservice/`.

2. **Add an `icon-map.json`** if your provider uses numeric or string icon codes. The file maps provider codes to local icon filenames:

    ```json
    {
        "sunny": "day/clear.png",
        "rainy": "rainy.png"
    }
    ```

    If your service produces icon paths directly, you can skip this file and override `get_icon()`.

3. **Implement `WeatherService`**:

    ```python
    # server/weather/myservice/myservice.py
    from ..service import WeatherService
    from ..registry import register

    @register("myservice")
    class MyWeatherService(WeatherService):
        def __init__(self, *, apikey=None, location=None, num_hours=6, metric=True):
            super().__init__(
                apikey=apikey,
                baseurl="https://api.myweatherprovider.example",
                service_name="myservice",
                num_hours=num_hours,
                metric=metric,
            )
            # any extra setup, e.g. resolving a location key

        def get_current_conditions(self) -> dict:
            ...

        def get_daily_summary(self) -> dict:
            ...

        def get_hourly_forecast(self) -> list:
            ...

        def get_5day_forecast(self) -> list:
            ...
    ```

    Only declare the constructor parameters your service actually uses — the registry filters kwargs automatically before passing them to your constructor.

4. **Import the module in `server.py`** so the `@register` decorator runs at startup:

    ```python
    import weather.myservice.myservice  # noqa: F401
    ```

5. **Select it in `config.yaml`**:

    ```yaml
    weather:
      service: myservice
      apikey: YOUR_API_KEY
    ```

### Return value shapes

The server views expect specific keys from each method. Use the built-in services as a reference; missing keys are generally handled gracefully (rendered as `N/A` or hidden), but the following are required by all page layouts:

**`get_current_conditions()`**
```python
{
    "icon": "icon/day/clear.png",          # relative path from server/views/html/
    "temperature": {
        "unit": "°C",                      # or "°F"
        "value": 18,
        "feels_like": 16,
    },
    "wind": {
        "unit": "kmh",                     # or "mph"
        "value": 12.4,
        "direction_degrees": 270,
    },
    "humidity": 64,                        # percent
    "uv_index": 3,                         # or None
    "weather_text": "Partly sunny",
}
```

**`get_daily_summary()`**
```python
{
    "icon": "icon/day/partly-clear.png",
    "temperature": {
        "unit": "°C",
        "min": 10,
        "max": 20,
        "feels_like": 18,
    },
    "wind": {"unit": "kmh", "value": 12.4},
    "humidity": 64,
    "rain_probability": 35,                # percent
    "pollen": [                            # or None
        {"name": "Grass", "category": "Low", "category_value": 1},
    ],
}
```

**`get_hourly_forecast()`** — list of `num_hours` entries:
```python
{
    "dt": datetime(2026, 6, 14, 9, 0),
    "icon": "icon/day/clear.png",
    "temperature": {"unit": "°C", "value": 16},
    "wind": {"unit": "kmh", "value": 10, "direction_degrees": 250},
    "humidity": 60,
    "rain_probability": 10,
}
```

**`get_5day_forecast()`** — list of 5 entries:
```python
{
    "dt": datetime(2026, 6, 14, 0, 0),
    "icon": "icon/day/partly-clear.png",
    "temperature": {"unit": "°C", "min": 10, "max": 20},
    "wind": {"unit": "kmh", "value": 12, "direction_degrees": 270},
    "rain_probability": 35,
    "uv_index": 4,
    "pollen": [...],                       # or None
    "sunrise": "06:15",
    "sunset": "21:30",
    "hours_of_sun": 8.5,
    "hours_of_rain": 1.2,
    "day_phrase": "Partly sunny with some afternoon clouds",
    "night_phrase": "Mostly cloudy",
}
```

For a complete working example, see [accuweather/accuweather.py](accuweather/accuweather.py) or [mock/mock.py](mock/mock.py).
