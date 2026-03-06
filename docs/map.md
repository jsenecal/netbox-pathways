# Map View

NetBox Pathways includes a built-in interactive map for visualizing structures and pathways.

## Accessing the Map

Navigate to **Plugins → Pathways → Map** or go directly to `/plugins/pathways/map/`.

## Features

- **Structure markers** — All structures with geographic locations are plotted as markers
- **Pathway lines** — All pathways with geographic paths are drawn as lines
- **Toggle layers** — Show/hide structures and pathways independently
- **Reset view** — Return to the default map center and zoom
- **Click interaction** — Click on structures or pathways for details

## Map Controls

| Button | Action |
|--------|--------|
| **Toggle Structures** | Show/hide structure markers |
| **Toggle Pathways** | Show/hide pathway lines |
| **Reset View** | Reset to the configured default center and zoom |

## Statistics

The map footer shows:

- **Structures** — Count of structures displayed
- **Pathways** — Count of pathways displayed
- **Total Length** — Sum of all displayed pathway lengths in km

## Legend

### Structure Types

| Color | Type |
|-------|------|
| Green | Pole |
| Blue | Manhole |
| Cyan | Handhole |
| Orange | Cabinet |
| Red | Building Entrance |

### Pathway Types

| Color / Style | Type |
|--------------|------|
| Brown solid | Conduit |
| Blue solid | Aerial |
| Gray solid | Direct Buried |
| Orange solid | Innerduct |
| Green solid | Cable Tray |

## Configuration

The default map center and zoom are configured in `PLUGINS_CONFIG`:

```python
PLUGINS_CONFIG = {
    'netbox_pathways': {
        'map_center_lat': 45.5017,
        'map_center_lon': -73.5673,
        'map_zoom': 10,
    }
}
```

The map center can also be overridden via URL parameters: `?lat=40.7128&lon=-74.0060&zoom=12`

## For Advanced GIS

The built-in map is intended for quick visualization. For advanced GIS workflows (spatial analysis, custom cartography, print layouts), use the [QGIS integration](qgis.md) which connects to the same data via GeoJSON API endpoints.
