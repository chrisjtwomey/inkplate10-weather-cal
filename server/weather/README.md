# Weather providers

Each weather provider is a class in its own folder here. A new provider plugs
in without a change to the rest of the server.

```
weather/
├── service.py       WeatherService, the class every provider subclasses
├── registry.py      the providers by name, and create()
├── accuweather/
├── meteireann/      Ireland only
├── openmeteo/
├── openweathermap/
└── mock/            made-up weather, for development and tests
```

## The providers

| `weather.service` | API | Key | Cache |
|---|---|---|---|
| `accuweather` | [AccuWeather](https://developer.accuweather.com/) | needed | 55 minutes |
| `meteireann` | [Met Éireann](https://data.gov.ie/dataset/met-eireann-forecast-api): the Harmonie model, ~2.5 km. Finds the location through Nominatim. | – | 55 minutes |
| `openmeteo` | [Open-Meteo](https://open-meteo.com/): worldwide, free for non-commercial use. Finds the location through its own geocoding. | – | 55 minutes |
| `openweathermap` | [OpenWeatherMap](https://openweathermap.org/api) | needed | none |
| `mock` | none: made-up but believable weather, with no network | – | none |

Every provider needs `location`. To get the keys, see
[doc/weather-apis.md](../../doc/weather-apis.md).

## How a provider fits in

`WeatherService` declares four abstract methods. A class that leaves one out
raises `TypeError` when the server creates it, not later at a render.

| Method | Returns |
|---|---|
| `get_current_conditions()` | The temperature, wind, humidity, UV index and weather text now. |
| `get_daily_summary()` | Today's high and low, chance of rain, pollen, wind and humidity. |
| `get_hourly_forecast()` | One entry an hour, for `num_hours` hours. |
| `get_5day_forecast()` | One entry a day, for 5 days. |

- `datasets()` gives these four to the pages by name: `current_conditions`, `daily_summary`, `hourly_forecasts` and `daily_forecasts`. A page fetches only what its `Page.requires` names.
- `get_icon(icon_key)` turns the provider's icon code into a local icon, through the provider's `icon-map.json`.
- `invalidate_forecast_cache()` does nothing by default. A provider that caches overrides it. The server calls it before each scheduled render, so each wake gets fresh weather.
- `needs_apikey` is `True` by default. A provider whose API needs no key sets it to `False`, and the server then starts without `weather.apikey`.

`registry.py` is backed by epd's `Registry`. `@register("name")` adds a
provider when its module is imported. `create(name, ...)` makes one, and passes
only the arguments its constructor declares.

## Adding a provider

1. Make a folder, such as `server/weather/myservice/`.
2. If the provider's icons are codes, add an `icon-map.json` that maps each code to a local icon:

    ```json
    {
        "sunny": "day/clear.png",
        "rainy": "rainy.png"
    }
    ```

    A provider that gives icon paths itself can override `get_icon()` instead.

3. Subclass `WeatherService`:

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

        def get_current_conditions(self) -> dict: ...
        def get_daily_summary(self) -> dict: ...
        def get_hourly_forecast(self) -> list: ...
        def get_5day_forecast(self) -> list: ...
    ```

    Declare only the constructor arguments the provider uses.

4. Import its module in `server.py`, so `@register` runs:

    ```python
    import weather.myservice.myservice  # noqa: F401
    ```

5. Choose it in `config.yaml`:

    ```yaml
    weather:
      service: myservice
      apikey: YOUR_API_KEY
    ```

## What each method returns

The pages need these keys. [mock/mock.py](mock/mock.py) returns every one of them,
and [accuweather/accuweather.py](accuweather/accuweather.py) is a full provider.

**`get_current_conditions()`**
```python
{
    "icon": "icon/day/clear.png",          # relative to server/views/html/
    "temperature": {"unit": "°C", "value": 18, "feels_like": 16},   # or "°F"
    "wind": {"unit": "kmh", "value": 12.4, "direction_degrees": 270},  # or "mph"
    "humidity": 64,                        # percent
    "uv_index": 3,                         # or None
    "weather_text": "Partly sunny",
}
```

**`get_daily_summary()`**
```python
{
    "icon": "icon/day/partly-clear.png",
    "temperature": {"unit": "°C", "min": 10, "max": 20, "feels_like": 18},
    "wind": {"unit": "kmh", "value": 12.4},
    "humidity": 64,
    "rain_probability": 35,                # percent
    "pollen": [                            # or None
        {"name": "Grass", "category": "Low", "category_value": 1},
    ],
}
```

**`get_hourly_forecast()`**: `num_hours` entries of
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

**`get_5day_forecast()`**: 5 entries of
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
