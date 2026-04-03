# Configuration

All plugin settings are configured in `PLUGINS_CONFIG` within your NetBox `configuration.py`.

## Required Settings

| Setting | Type  | Description |
|---------|-------|-------------|
| `srid`  | `int` | Spatial reference system ID for stored geometries (e.g. `3348` for NAD83(CSRS)) |

## Map Settings

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'srid': 3348,
        'map_center_lat': 45.5,
        'map_center_lon': -73.5,
        'map_zoom': 13,
    }
}
```

| Setting              | Type    | Default                         | Description                              |
|----------------------|---------|---------------------------------|------------------------------------------|
| `map_center_lat`     | `float` | `45.5017`                       | Default latitude for the map center      |
| `map_center_lon`     | `float` | `-73.5673`                      | Default longitude for the map center     |
| `map_zoom`           | `int`   | `10`                            | Default zoom level (1-22)                |
| `map_tiles`          | `str`   | OpenStreetMap URL               | Tile URL template (fallback, see below)  |
| `map_max_native_zoom`| `int`   | `19`                            | Max native zoom for fallback tiles       |
| `map_attribution`    | `str`   | `© OpenStreetMap contributors`  | Attribution for fallback tiles           |
| `map_base_layers`    | `list`  | —                               | Custom base layer definitions (see below)|
| `map_overlays`       | `list`  | `[]`                            | WMS/WMTS/tile overlay layers             |

## Tile Providers

By default the plugin uses OpenStreetMap tiles. For better zoom levels, dark mode support, and satellite imagery, we recommend configuring Mapbox base layers via the Styles API. A free Mapbox account provides 200,000 tile requests/month.

### Mapbox (recommended)

Set `map_base_layers` with one or more Mapbox style URLs. Each entry is a dict with `name`, `url`, and Leaflet tile layer options. The plugin passes these to both the interactive map and the form geometry widgets.

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'srid': 3348,
        'map_base_layers': [
            {
                'name': 'Dark',
                'url': 'https://api.mapbox.com/styles/v1/mapbox/navigation-night-v1/tiles/{z}/{x}/{y}?access_token=YOUR_TOKEN',
                'tileSize': 512,
                'zoomOffset': -1,
                'attribution': '&copy; <a href="https://www.mapbox.com/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
                'maxNativeZoom': 22,
            },
            {
                'name': 'Light',
                'url': 'https://api.mapbox.com/styles/v1/mapbox/light-v11/tiles/{z}/{x}/{y}?access_token=YOUR_TOKEN',
                'tileSize': 512,
                'zoomOffset': -1,
                'attribution': '&copy; <a href="https://www.mapbox.com/">Mapbox</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
                'maxNativeZoom': 22,
            },
            {
                'name': 'Satellite',
                'url': 'https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{z}/{x}/{y}?access_token=YOUR_TOKEN',
                'tileSize': 512,
                'zoomOffset': -1,
                'attribution': '&copy; <a href="https://www.mapbox.com/">Mapbox</a>',
                'maxNativeZoom': 22,
            },
        ],
    },
}
```

Available Mapbox styles include `light-v11`, `dark-v11`, `streets-v12`, `outdoors-v12`, `satellite-v9`, `satellite-streets-v12`, `navigation-day-v1`, and `navigation-night-v1`. See [Mapbox Styles documentation](https://docs.mapbox.com/api/maps/styles/) for the full list.

The tile URLs use the Mapbox Styles API (`/styles/v1/`), which renders vector styles as raster tiles — required for Leaflet compatibility. Set `tileSize: 512` and `zoomOffset: -1` for Mapbox 512px tiles.

### OpenStreetMap (default)

When `map_base_layers` is not set, the plugin falls back to OpenStreetMap street tiles and Esri satellite imagery. You can customise the street tile URL with `map_tiles`:

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'srid': 3348,
        'map_tiles': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        'map_max_native_zoom': 19,
        'map_attribution': '&copy; OpenStreetMap contributors',
    },
}
```

Note that OSM tiles are limited to zoom level 19, while Mapbox supports up to 22.

## Auto-Registered Django Apps

The plugin automatically registers these Django apps via `PluginConfig.django_apps`:

- `django.contrib.gis` — Geographic model fields and spatial queries
- `rest_framework_gis` — GeoJSON serializer support for the REST API

You do not need to add these to `INSTALLED_APPS` manually.

## Dependencies

| Package                    | Version  | Purpose                    |
|----------------------------|----------|----------------------------|
| `djangorestframework-gis`  | `>=1.2`  | GeoJSON REST API responses |

## URL Parameters

The interactive map accepts optional URL query parameters that override the configured defaults:

| Parameter | Description                     | Example         |
|-----------|---------------------------------|-----------------|
| `lat`     | Override center latitude        | `?lat=40.7`     |
| `lon`     | Override center longitude       | `?lon=-74.0`    |
| `zoom`    | Override zoom level             | `?zoom=15`      |
| `bbox`    | Set bounding box (W,S,E,N)     | `?bbox=-74,40,-73,41` |
