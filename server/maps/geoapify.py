"""Geoapify Static Maps API, in a grey style that reads well on the panel."""
from urllib.parse import urlencode

from .geocode import open_meteo_centre
from .source import download

URL = "https://maps.geoapify.com/v1/staticmap"
# MapLibre zoom 9 on 512 px tiles shows the area of Google's zoom 10.
ZOOM = 9

_ROAD = "#808080"
_FILLS = ("highway-trunk", "highway-primary", "highway-secondary-tertiary", "highway-minor", "highway-link",
          "highway-motorway-link", "bridge-trunk-primary", "bridge-secondary-tertiary", "bridge-link",
          "bridge-motorway-link", "tunnel-trunk-primary", "tunnel-secondary-tertiary", "tunnel-minor")
_MOTORWAYS = ("highway-motorway", "bridge-motorway", "tunnel-motorway")
_CASINGS = ("highway-motorway-casing", "highway-trunk-casing", "highway-primary-casing",
            "highway-secondary-tertiary-casing", "highway-minor-casing", "highway-link-casing",
            "highway-motorway-link-casing", "bridge-motorway-casing", "bridge-trunk-primary-casing",
            "bridge-secondary-tertiary-casing", "bridge-link-casing", "bridge-motorway-link-casing",
            "tunnel-motorway-casing", "tunnel-trunk-primary-casing", "tunnel-secondary-tertiary-casing",
            "tunnel-minor-casing")
_PLACES = ("place-city", "place-town", "place-village", "place-other")

# The API takes whole-number sizes only.
STYLE = "|".join(
    ["water:#666666"]
    + [f"{layer}:{_ROAD};1" for layer in _FILLS]
    + [f"{layer}:{_ROAD};2" for layer in _MOTORWAYS]
    + [f"{layer}:{_ROAD};0" for layer in _CASINGS]
    + [f"{layer}:#000000" for layer in _PLACES]
)


class GeoapifyMaps:
    centres_on_a_name = False

    def __init__(self, apikey):
        self.apikey = apikey

    def centre(self, place):
        return open_meteo_centre(place)

    def image_url(self, centre):
        lat, lon = centre.split(",")
        return URL + "?" + urlencode({
            "style": "osm-bright-grey", "styleCustomization": STYLE, "width": 600, "height": 600,
            "center": f"lonlat:{lon},{lat}", "zoom": ZOOM, "scaleFactor": 2, "format": "png",
            "apiKey": self.apikey,
        })

    def fetch(self, url):
        return download(url)
