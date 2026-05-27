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
