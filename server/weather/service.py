import os
import json


class WeatherService:
    def __init__(
        self, apikey, baseurl, service_name, num_hours=6, metric=True
    ):
        self.baseurl = baseurl
        self.service_name = service_name
        self.apikey = apikey
        self.units = "metric" if metric else "imperial"
        self.num_hours = num_hours

    def get_icon(self, icon_key):
        icon_key = str(icon_key)

        cwd = os.path.dirname(os.path.realpath(__file__))
        mapfile_path = os.path.join(
            cwd, "..", f"weather/{self.service_name}/icon-map.json"
        )
        icon_map = None
        with open(mapfile_path) as f:
            icon_map = json.load(f)

        if icon_key not in icon_map:
            return ""

        return f"icon/{icon_map[icon_key]}"

    def get_daily_summary(self):
        raise NotImplementedError("get_current_conditions not implemented")

    def get_hourly_forecast(self):
        raise NotImplementedError("get_forecast not implemented")
