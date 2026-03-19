# Configuration

All plugin settings are configured in `PLUGINS_CONFIG` within your NetBox `configuration.py`.

## Settings

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'map_center_lat': 45.5,
        'map_center_lon': -73.5,
        'map_zoom': 13,
    }
}
```

| Setting          | Type    | Default | Description                          |
|------------------|---------|---------|--------------------------------------|
| `map_center_lat` | `float` | `45.5`  | Default latitude for the map center  |
| `map_center_lon` | `float` | `-73.5` | Default longitude for the map center |
| `map_zoom`       | `int`   | `13`    | Default zoom level (1-18)            |

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
