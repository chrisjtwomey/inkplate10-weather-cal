# Google Static Maps API Setup

This document covers Google Static Maps setup used by the server.

## Google Static Maps API

To generate a static map of your area, sign up to [Google's developer console](https://developers.google.com/):

1. Create a new project.
2. Go to Google Maps Platform -> `Maps Static API` -> `Enable`.
3. Go to `Credentials` -> `Create Credentials` -> `API Key`.
4. After generating your API key, update `google.apikey` in `config.yaml`.
5. Optional: restrict the API key to the `Maps Static API` service.

### Optional: replicate the map style used in this project

1. In Google Maps Platform -> `Map styles` -> `Create style`.
2. Select `Import JSON` and paste the contents of [../server/google/staticmaps/map-style.json](../server/google/staticmaps/map-style.json).
3. Click `Save` and assign a name to the map style.

### Create and configure a Map ID

1. In Google Maps Platform -> `Map management` -> `Create Map ID`.
2. Give the Map ID a name and set `map type` to `static`, then click `Save`.
3. Set the associated map style to the one created above.
4. Copy the Map ID and update `google.staticmaps_id` in `config.yaml`.
