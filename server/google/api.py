import time
import requests
from PIL import Image
from googlemaps import Client, timezone


class GoogleAPIService:
    def __init__(self, key):
        self.apikey = key
        self.client = Client(key)

    def get_timezone(self, location):
        tz = timezone(self.client, location)
        print(tz)
        return tz

    def get_static_map_url(self, map_id, location):
        svc = self.StaticMapService(self.apikey, map_id)
        return svc.get_url(location)

    class StaticMapService:
        DEFAULT_ZOOM = 10

        def __init__(self, apikey, map_id, cache=True):
            self.base_url = "https://maps.googleapis.com/maps/api/staticmap"
            self.apikey = apikey
            self.map_id = map_id
            self.scale = 2

            self.map_width = 600
            self.map_height = 600

            self.cache = cache

        def get_url(self, location, zoom=DEFAULT_ZOOM):
            no_cache_param = ""
            if not self.cache:
                no_cache_param = "&time={}".format(time.time())

            url = "{}?center={}&zoom={}&size={}x{}&key={}&map_id={}&scale={}&sensor=false{}".format(
                self.base_url,
                location,
                zoom,
                self.map_width,
                self.map_height,
                self.apikey,
                self.map_id,
                self.scale,
                no_cache_param,
            )

            return url

        def get_image(self, location, zoom=DEFAULT_ZOOM):
            r = requests.get(self.get_url(location, zoom))
            img = Image.open(r.raw)

            return img
