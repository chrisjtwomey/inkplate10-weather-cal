# Google Static Maps

The pages show a map of your area from Google's
[Maps Static API](https://developers.google.com/maps/documentation/maps-static/overview).
The server needs an API key and a map ID.

## The API key

1. In [Google's developer console](https://console.cloud.google.com/), create a project.
2. In Google Maps Platform, enable the **Maps Static API**. Also enable the **Geocoding API** to centre the map on exact coordinates. Without it, Google centres the map on the place name.
3. In **Credentials**, create an **API key**. You can restrict it to these APIs.

## The map style (optional)

For the style of the pictures in the main README:

1. In Google Maps Platform, open **Map styles** and **Create style**.
2. Choose **Import JSON**, and paste [server/google/staticmaps/map-style.json](../server/google/staticmaps/map-style.json).
3. Save it, with a name.

## The map ID

1. In Google Maps Platform, open **Map management** and **Create Map ID**.
2. Give it a name, set **Map type** to **Static**, and save it.
3. Set its map style to the one you made.

```yaml
google:
  apikey: YOUR_API_KEY
  staticmaps_mapid: YOUR_MAP_ID
```
