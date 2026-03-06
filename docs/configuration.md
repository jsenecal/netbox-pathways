# Configuration

## Plugin Settings

Add these to `PLUGINS_CONFIG` in your NetBox `configuration.py`:

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'map_center_lat': 45.5017,    # Default map center latitude
        'map_center_lon': -73.5673,   # Default map center longitude
        'map_zoom': 10,               # Default map zoom level (1-18)
    }
}
```

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `map_center_lat` | float | `45.5017` | Latitude for the default map center |
| `map_center_lon` | float | `-73.5673` | Longitude for the default map center |
| `map_zoom` | int | `10` | Default zoom level for the map view |

## Django Apps

The plugin automatically registers these Django apps via `PluginConfig.django_apps`:

- `django.contrib.gis` — GeoDjango spatial framework
- `rest_framework_gis` — GeoJSON serialization for the REST API

You do **not** need to add these to `INSTALLED_APPS` manually.

## Dependencies

The plugin installs:

- `djangorestframework-gis>=1.2.0` — GeoJSON API serialization

All other dependencies (Django, DRF, PostGIS backend) are provided by NetBox itself.
