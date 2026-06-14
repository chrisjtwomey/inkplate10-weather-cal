"""Registry for pluggable weather service implementations.

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

import inspect
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weather.service import WeatherService

_REGISTRY: dict[str, type["WeatherService"]] = {}


def register(name: str):
    """Class decorator that registers a WeatherService implementation.

    Args:
        name: The identifier used in config (e.g. ``"accuweather"``).
    """
    def decorator(cls):
        _REGISTRY[name] = cls
        return cls
    return decorator


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

    Args:
        name: Registered service name (e.g. ``"accuweather"``).
        apikey: API key forwarded to the service constructor.
        location: Location string forwarded to the service constructor.
        num_hours: Number of hourly forecast entries.
        metric: True for metric units, False for imperial.
        **kwargs: Extra keyword arguments forwarded to the service constructor,
            allowing service-specific parameters without modifying this function.

    Raises:
        ValueError: If *name* is not in the registry.
    """
    if name not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY.keys())) or "(none registered)"
        raise ValueError(
            f"Unknown weather service {name!r}. Supported: {supported}"
        )

    cls = _REGISTRY[name]
    all_kwargs: dict[str, Any] = dict(
        apikey=apikey,
        location=location,
        num_hours=num_hours,
        metric=metric,
        **kwargs,
    )
    # Only forward kwargs that the constructor actually declares, so services
    # don't need to accept parameters they don't use.  If the constructor
    # itself accepts **kwargs, pass everything through unfiltered.
    sig = inspect.signature(cls.__init__)
    params = sig.parameters
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )
    filtered = all_kwargs if has_var_keyword else {k: v for k, v in all_kwargs.items() if k in params}
    return cls(**filtered)


def registered_services() -> tuple[str, ...]:
    """Return a tuple of all registered service names."""
    return tuple(_REGISTRY.keys())
