# Weather providers

Choose one, and set it in the server's `config.yaml` as `weather.service`.

| Provider | Where | API key |
|---|---|---|
| [AccuWeather](#accuweather) | worldwide | needed |
| [Met Éireann](#met-éireann) | Ireland only | – |
| [Open-Meteo](#open-meteo) | worldwide, free for non-commercial use | – |
| [OpenWeatherMap](#openweathermap) | worldwide | needed |

Each provider finds the place from `location` in the same config. The map
needs a Google key too: see [google-static-maps.md](google-static-maps.md).

## AccuWeather

1. Sign up at [developer.accuweather.com](https://developer.accuweather.com/).
2. [Create an app](https://developer.accuweather.com/user/me/apps), with a few words on what it is for.
3. Generate an API key.

```yaml
weather:
  service: accuweather
  apikey: YOUR_API_KEY
```

The server caches the answers for 55 minutes, to make fewer calls.

## Met Éireann

Forecasts from the Harmonie model, at about 2.5 km, blending into ECMWF after
about 48 hours. Outside Ireland it has only the ECMWF data, so the forecast is
coarser.

```yaml
weather:
  service: meteireann
location: Dublin
```

The server finds the place through [Nominatim](https://nominatim.openstreetmap.org/).

## Open-Meteo

Forecasts from several models, such as ECMWF, GFS and DWD ICON, at 1–11 km
depending on the region.

```yaml
weather:
  service: openmeteo
location: London
```

The server finds the place through Open-Meteo's own geocoding.

## OpenWeatherMap

Sign up at OpenWeatherMap and [generate an API key](https://home.openweathermap.org/api_keys).

```yaml
weather:
  service: openweathermap
  apikey: YOUR_API_KEY
```

## Another provider

To add a provider, see [server/weather/README.md](../server/weather/README.md).
