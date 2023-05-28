import requests
from datetime import datetime
from ..service import WeatherService


class OpenWeatherMapService(WeatherService):
    def __init__(self, apikey, location, num_hours=6, metric=True, mock=False):
        super().__init__(
            apikey,
            "https://api.openweathermap.org",
            "openweathermap",
            num_hours,
            metric,
        )
        self.lat, self.lon = self._get_location_coords(location)

    def get_daily_summary(self):
        data = None
        res = requests.get(
            self.baseurl
            + "/data/2.5/weather?lat={}&lon={}&appid={}&units={}".format(
                self.lat, self.lon, self.apikey, self.units
            )
        )
        data = res.json()

        if self.units == "metric":
            units = "\N{DEGREE SIGN}C"
        else:
            units = ("\N{DEGREE SIGN}F",)

        forecast = {
            "icon": self.get_icon(data["weather"][0]["icon"]),
            "temperature": {
                "unit": units,
                "min": round(data["main"]["temp_min"]),
                "max": round(data["main"]["temp_max"]),
            },
        }

        return forecast

    def get_hourly_forecast(self):
        data = None
        res = requests.get(
            self.baseurl
            + "/data/2.5/forecast?cnt={}&lat={}&lon={}&appid={}&units={}".format(
                self.num_hours, self.lat, self.lon, self.apikey, self.units
            )
        )
        data = res.json()

        code = data["cod"]
        if int(code) != 200:
            raise ValueError("Non-200 response from weather api: {}".format(data))

        if self.units == "metric":
            temp_units = "\N{DEGREE SIGN}C"
            speed_units = "kmh"
        else:
            temp_units = "\N{DEGREE SIGN}F"
            speed_units = "mph"

        forecasts = []
        for entry in data["list"]:
            forecast = {
                "dt": datetime.fromtimestamp(entry["dt"]),
                "icon": self.get_icon(entry["weather"][0]["icon"]),
                "temperature": {
                    "unit": temp_units,
                    "value": round(entry["main"]["feels_like"]),
                },
                "wind": {
                    "unit": speed_units,
                    "real": entry["wind"]["speed"],
                },
                "humidity": entry["main"]["humidity"],
                "rain_probability": round(entry["pop"] * 100),
            }

            forecasts.append(forecast)

        return forecasts

    def _get_location_coords(self, location):
        data = None

        if self.mock:
            import os, json

            path = os.path.join(
                os.path.dirname(os.path.realpath(__file__)),
                "samples/mock-sample-location.json",
            )
            with open(path, encoding="utf8") as f:
                data = json.load(f)
        else:
            res = requests.get(
                self.baseurl
                + "/geo/1.0/direct?q={}&limit=1&appid={}".format(location, self.apikey)
            )
            data = res.json()

        if len(data) == 0 or len(data) > 1:
            raise ValueError("Unexpected response from weather api: {}".format(data))

        data = data[0]
        lat = round(data["lat"])
        lon = round(data["lon"])

        return lat, lon
