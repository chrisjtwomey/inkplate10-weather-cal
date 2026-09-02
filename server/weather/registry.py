"""Registry for pluggable weather service implementations.

Backed by the generic ``epd_server.registry.Registry``; this module holds the
one instance weather providers register into, and keeps the weather-flavoured
``create()`` defaults.

Usage — registering a service:

    from weather.registry import register

    @register("myservice")
    class MyWeatherService(WeatherService):
        def __init__(self, *, apikey=None, location=None, num_hours=6, metric=True):
            ...

Usage — creating a service from config:

    from weather.registry import create

    weather_svc = create(
        cfg.weather_service,
        apikey=cfg.weather_apikey,
        location=cfg.location,
        num_hours=cfg.num_hourly_forecasts,
        metric=cfg.weather_metric,
    )
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from epd_server.registry import Registry

if TYPE_CHECKING:
    from weather.service import WeatherService

_registry = Registry("weather service")

# The raw name -> class mapping. Tests inspect it directly.
_REGISTRY: dict[str, type["WeatherService"]] = _registry._items

register = _registry.register


def create(
    name: str,
    *,
    apikey: str | None = None,
    location: str | None = None,
    num_hours: int = 6,
    metric: bool = True,
    **kwargs,
) -> "WeatherService":
    """Instantiate a registered WeatherService by name.

    Only the keyword arguments the constructor declares are forwarded, so
    services need not accept parameters they do not use.

    Raises:
        ValueError: If *name* is not in the registry.
    """
    return _registry.create(
        name,
        apikey=apikey,
        location=location,
        num_hours=num_hours,
        metric=metric,
        **kwargs,
    )


def registered_services() -> tuple[str, ...]:
    """Return a tuple of all registered service names."""
    return _registry.names()
