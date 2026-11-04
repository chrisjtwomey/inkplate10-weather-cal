"""The map on the today, current and tomorrow pages."""
from .geoapify import GeoapifyMaps
from .google import GoogleMaps
from .openfreemap import OpenFreeMap
from .source import MapCache, MapFetchError, StaticMapSource

MAP_PROVIDERS = ("google", "geoapify", "openfreemap")


def create_provider(name, *, google_apikey=None, staticmaps_mapid=None, geoapify_apikey=None):
    """The provider ``name`` from MAP_PROVIDERS, with its keys."""
    if name == "google":
        return GoogleMaps(google_apikey, staticmaps_mapid)
    if name == "geoapify":
        return GeoapifyMaps(geoapify_apikey)
    if name == "openfreemap":
        return OpenFreeMap()
    raise ValueError(f"no map provider {name!r}")


__all__ = ["MAP_PROVIDERS", "MapCache", "MapFetchError", "StaticMapSource", "create_provider"]
