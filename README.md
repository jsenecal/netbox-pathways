# NetBox Fiber Plugin

A comprehensive NetBox plugin for documenting fiber optic networks with PostGIS integration, providing geographic tracking of conduits, structures (poles, manholes), and cable positioning.

## Features

- **PostGIS Integration**: Full geographic information system support for spatial data
- **Infrastructure Management**: Track poles, manholes, cabinets, and other fiber structures
- **Conduit Tracking**: Document underground and aerial conduit paths with capacity management
- **Cable Integration**: Extends NetBox's existing cable functionality with geographic routing
- **Interactive Mapping**: Leaflet-based maps for visualizing fiber infrastructure
- **Bulk Import/Export**: Support for importing GIS data from external sources

## Requirements

- NetBox 3.7.0 or higher
- PostgreSQL with PostGIS extension
- Python 3.10+

## Installation

1. Install the plugin package:
```bash
pip install netbox-fiber
```

2. Add the plugin to your NetBox configuration:
```python
# configuration.py
PLUGINS = ['netbox_fiber']

PLUGINS_CONFIG = {
    'netbox_fiber': {
        'map_center_lat': 39.8283,  # Default map center latitude
        'map_center_lon': -98.5795,  # Default map center longitude
        'map_zoom': 5,               # Default map zoom level
        'enable_3d_view': False,     # Enable 3D visualization (future feature)
    }
}
```

3. Run database migrations:
```bash
python manage.py migrate
```

4. Collect static files:
```bash
python manage.py collectstatic
```

5. Restart NetBox services

## Development Setup

### Using DevContainers

1. Clone the repository:
```bash
git clone https://github.com/yourusername/netbox-fiber-plugin.git
cd netbox-fiber-plugin
```

2. Open in VS Code with DevContainers extension
3. VS Code will automatically build and start the development environment

### Manual Setup

1. Install dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Start PostgreSQL with PostGIS:
```bash
docker run -d \
  --name netbox-postgres \
  -e POSTGRES_DB=netbox \
  -e POSTGRES_USER=netbox \
  -e POSTGRES_PASSWORD=netbox \
  -p 5432:5432 \
  postgis/postgis:15-3.3
```

3. Start Redis:
```bash
docker run -d \
  --name netbox-redis \
  -p 6379:6379 \
  redis:7-alpine
```

## Usage

### Managing Structures

1. Navigate to **Plugins → NetBox Fiber → Structures**
2. Click **Add** to create a new structure
3. Select the structure type (pole, manhole, cabinet, etc.)
4. Use the map interface to set the geographic location
5. Fill in additional details and save

### Creating Conduits

1. Navigate to **Plugins → NetBox Fiber → Conduits**
2. Click **Add** to create a new conduit
3. Select start and end structures
4. Draw the conduit path on the map
5. Specify conduit type, material, and capacity
6. Save the conduit

### Viewing the Fiber Map

1. Navigate to **Plugins → NetBox Fiber → Fiber Map**
2. Use the interactive map to:
   - View all structures and conduits
   - Filter by type or site
   - Click on elements for details
   - Toggle layer visibility

### Linking Cables to Conduits

1. When creating or editing a cable in NetBox
2. Navigate to the **Fiber Segments** tab
3. Add segments to define the cable's path through conduits
4. Specify entry/exit points and slack loops

## API Endpoints

The plugin provides REST API endpoints for all models:

- `/api/plugins/netbox-fiber/structures/` - Fiber structures
- `/api/plugins/netbox-fiber/conduits/` - Fiber conduits
- `/api/plugins/netbox-fiber/splices/` - Fiber splices
- `/api/plugins/netbox-fiber/cable-segments/` - Cable segments

## Models

### FiberStructure
- Physical structures in the fiber network
- Types: poles, manholes, handholes, cabinets, vaults, pedestals, building entrances, splice closures
- Geographic location (PostGIS Point)
- Site association
- Elevation tracking

### FiberConduit
- Conduit paths between structures
- Types: underground, aerial, submarine, direct buried, indoor
- Materials: PVC, HDPE, steel, concrete, fiberglass
- Geographic path (PostGIS LineString)
- Capacity management

### FiberSplice
- Splice points and enclosures
- Associated with structures
- Fiber count tracking

### FiberCableSegment
- Links NetBox cables to conduits
- Sequential path tracking
- Slack loop management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

Apache 2.0 License