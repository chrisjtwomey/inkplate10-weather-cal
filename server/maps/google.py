"""Google Maps Static API, styled by a map ID."""
import logging

from googlemaps import Client
from googlemaps.exceptions import ApiError
from googlemaps.geocoding import geocode

from .source import download

log = logging.getLogger(__name__)

URL = "https://maps.googleapis.com/maps/api/staticmap"
ZOOM = 10


class GoogleMaps:
    centres_on_a_name = True

    def __init__(self, apikey, map_id):
        self.apikey = apikey
        self.map_id = map_id
        self.client = Client(apikey)

    def centre(self, place):
        try:
            found = geocode(self.client, place)
        except ApiError as exc:
            # Google's answer, as for a key without the Geocoding API. It
            # would give the same answer again, so the name is kept.
            log.warning("Google will not look up %s: %s", place, exc.status)
            return place
        except Exception as exc:  # noqa: BLE001 - the name still gives a map
            log.warning("Could not look up %s: %s", place, type(exc).__name__)
            return None
        if not found:
            return place
        point = found[0]["geometry"]["location"]
        return "{:.6f},{:.6f}".format(point["lat"], point["lng"])

    def image_url(self, centre):
        # Unencoded, as the cache keeps it: a new form would fetch every kept map again.
        return f"{URL}?center={centre}&zoom={ZOOM}&size=600x600&key={self.apikey}" \
               f"&map_id={self.map_id}&scale=2&sensor=false"

    def fetch(self, url):
        return download(url)
