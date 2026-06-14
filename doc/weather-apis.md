# Weather API Setup

This document covers weather provider API setup used by the server.

## AccuWeather API

To obtain an API key:

1. Sign up to [developer.accuweather.com](https://developer.accuweather.com/).
2. Create an app in [https://developer.accuweather.com/user/me/apps](https://developer.accuweather.com/user/me/apps).
3. Enter details about your app's usage and purpose.
4. Generate an API key.

Update your server config:

- `weather.apikey`: your generated API key
- `weather.service`: `accuweather`

> **Note:** AccuWeather API responses are cached server-side to minimize API calls between image regenerations.

## OpenWeatherMap API

To obtain an API key, sign up to OpenWeatherMap and [generate an API key](https://home.openweathermap.org/api_keys).

Update your server config:

- `weather.apikey`: your generated API key
- `weather.service`: `openweathermap`

For Google Static Maps setup, see [google-static-maps.md](google-static-maps.md).

## Custom weather service

The server uses a pluggable interface — any weather source can be added without modifying the core server code. See [server/weather/README.md](../server/weather/README.md) for a step-by-step guide.

## Met Éireann API

Met Éireann's forecast API is based on the [MET Norway metno-wdb2ts](https://data.gov.ie/dataset/met-eireann-forecast-api) stack and provides forecasts driven by the **Harmonie NWP model** (~2.5 km resolution) for Ireland, blending into ECMWF beyond ~48 hours. It is free to use with **no API key required**.

> **Note:** This service provides forecasts for **Ireland only**. Using it with a non-Irish location will return degraded results (ECMWF only, no Harmonie model data).

Update your server config:

```yaml
weather:
  service: meteireann
  # no apikey needed
```

Location is geocoded automatically via [Nominatim](https://nominatim.openstreetmap.org/) using the `location` value already set in your config:

```yaml
location: Dublin
```
