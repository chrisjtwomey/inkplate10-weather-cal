import requests
from collections import defaultdict
from datetime import datetime, time as dt_time
from ..service import WeatherService


class OpenWeatherMapService(WeatherService):
    def __init__(self, apikey, location, num_hours=6, metric=True):
        super().__init__(
            apikey,
            "https://api.openweathermap.org",
            "openweathermap",
            num_hours,
            metric,
        )
        self.lat, self.lon = self._get_location_coords(location)

    def get_daily_summary(self):
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
            "pollen": None,
        }

        return forecast

    def get_current_conditions(self):
        res = requests.get(
            self.baseurl
            + "/data/2.5/weather?lat={}&lon={}&appid={}&units={}".format(
                self.lat, self.lon, self.apikey, self.units
            )
        )
        data = res.json()

        if self.units == "metric":
            temp_unit = "\N{DEGREE SIGN}C"
            speed_unit = "kmh"
        else:
            temp_unit = "\N{DEGREE SIGN}F"
            speed_unit = "mph"

        return {
            "icon": self.get_icon(data["weather"][0]["icon"]),
            "temperature": {
                "unit": temp_unit,
                "value": round(data["main"]["temp"]),
                "feels_like": round(data["main"]["feels_like"]),
            },
            "wind": {
                "unit": speed_unit,
                "value": data["wind"]["speed"],
                "direction_degrees": data["wind"].get("deg", 0),
            },
            "humidity": data["main"]["humidity"],
            "uv_index": None,  # requires separate /onecall endpoint
            "weather_text": data["weather"][0].get("description", "").capitalize(),
        }

    def get_hourly_forecast(self):
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
                    "value": entry["wind"]["speed"],
                    "direction_degrees": entry["wind"].get("deg", 0),
                },
                "humidity": entry["main"]["humidity"],
                "rain_probability": round(entry["pop"] * 100),
            }

            forecasts.append(forecast)

        return forecasts

    def get_5day_forecast(self):
        res = requests.get(
            self.baseurl
            + "/data/2.5/forecast?cnt=40&lat={}&lon={}&appid={}&units={}".format(
                self.lat, self.lon, self.apikey, self.units
            )
        )
        data = res.json()

        code = data["cod"]
        if int(code) != 200:
            raise ValueError("Non-200 response from weather api: {}".format(data))

        if self.units == "metric":
            temp_unit = "\N{DEGREE SIGN}C"
            speed_unit = "kmh"
        else:
            temp_unit = "\N{DEGREE SIGN}F"
            speed_unit = "mph"

        # Group 3-hour entries by calendar date
        by_date = defaultdict(list)
        for entry in data["list"]:
            day = datetime.fromtimestamp(entry["dt"]).date()
            by_date[day].append(entry)

        dates = sorted(by_date.keys())[:5]

        forecasts = []
        for day in dates:
            entries = by_date[day]
            # Use the entry closest to noon as the representative for icon/wind
            noon_entry = min(
                entries,
                key=lambda e: abs(datetime.fromtimestamp(e["dt"]).hour - 12),
            )
            temps = [e["main"]["temp"] for e in entries]

            forecasts.append({
                "dt": datetime.combine(day, dt_time(0, 0)),
                "icon": self.get_icon(noon_entry["weather"][0]["icon"]),
                "temperature": {
                    "unit": temp_unit,
                    "min": round(min(temps)),
                    "max": round(max(temps)),
                },
                "wind": {
                    "unit": speed_unit,
                    "value": noon_entry["wind"]["speed"],
                    "direction_degrees": noon_entry["wind"].get("deg", 0),
                },
                "rain_probability": round(max(e["pop"] for e in entries) * 100),
                "uv_index": None,
                "pollen": None,
                "sunrise": None,
                "sunset": None,
                "hours_of_sun": None,
                "hours_of_rain": None,
                "day_phrase": None,
                "night_phrase": None,
            })

        return forecasts

    def _get_location_coords(self, location):
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
