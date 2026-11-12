# Maps

Each page shows a map of your `location` at the top, unless its `picture`
setting shows a photo instead. Set `map.provider` to one of these:

| Provider | Cost | Key |
|---|---|---|
| [Google](#google) (default) | free up to a monthly limit, then paid; needs a card | API key and map ID |
| [Geoapify](#geoapify) | free up to 3,000 credits a day; no card | API key |
| [OpenFreeMap](#openfreemap) | free | – |

The server fetches the map once for each location and provider, and keeps it
in `data/map-cache`. Each map image has the provider's credit line at its
bottom edge.

## Google

The map comes from Google's
[Maps Static API](https://developers.google.com/maps/documentation/maps-static/overview).
The server needs an API key and a map ID.

### The API key

1. In [Google's developer console](https://console.cloud.google.com/), create a project.
2. In Google Maps Platform, enable the **Maps Static API**. Also enable the **Geocoding API** to centre the map on exact coordinates. Without it, Google centres the map on the place name.
3. In **Credentials**, create an **API key**. You can restrict it to these APIs.

### The map style (optional)

For the style of the pictures in the main README:

1. In Google Maps Platform, open **Map styles** and **Create style**.
2. Choose **Import JSON**, and paste [server/maps/google-map-style.json](../server/maps/google-map-style.json).
3. Save it, with a name.

### The map ID

1. In Google Maps Platform, open **Map management** and **Create Map ID**.
2. Give it a name, set **Map type** to **Static**, and save it.
3. Set its map style to the one you made.

```yaml
map:
  provider: google
google:
  apikey: YOUR_API_KEY
  staticmaps_mapid: YOUR_MAP_ID
```

## Geoapify

The map comes from Geoapify's
[Static Maps API](https://apidocs.geoapify.com/docs/maps/static/), in its
`osm-bright-grey` style with darker water and thinner roads, for the panel's
four greys.

1. Sign up at [myprojects.geoapify.com](https://myprojects.geoapify.com/).
2. Create a project. Its API key is on the project's page.

```yaml
map:
  provider: geoapify
geoapify:
  apikey: YOUR_API_KEY
```

The server finds the place's coordinates with Open-Meteo's place search, which
needs no key.

## OpenFreeMap

[OpenFreeMap](https://openfreemap.org/) serves map data, not pictures, so the
server draws the map itself: it opens the `bright` style in the same Chromium
that renders the pages, and saves the result. This takes a few seconds, once
for each location. The server gives the style the same water, roads and place
names as the Geoapify map.

The server needs to reach `tiles.openfreemap.org` for the map, and `unpkg.com`
for [MapLibre](https://maplibre.org/), the script that draws it. The server
checks the script against a fixed hash, and does not run a changed copy.

```yaml
map:
  provider: openfreemap
```

The server finds the place's coordinates with Open-Meteo's place search.

On macOS, run the server in Docker for this provider. Chrome on macOS cannot
draw the map with the flags the renderer starts it with, so the page has no
map.
