# REST API

NetBox Pathways extends NetBox's REST API with endpoints for all models. All endpoints follow standard NetBox API conventions — token authentication, pagination, filtering, and nested serialization.

## Authentication

Use a NetBox API token:

```bash
curl -H "Authorization: Token <your-token>" \
  https://your-netbox/api/plugins/pathways/structures/
```

## Endpoints

### Standard CRUD Endpoints

| Endpoint | Model | Methods |
|----------|-------|---------|
| `/api/plugins/pathways/structures/` | Structure | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/conduit-banks/` | ConduitBank | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/pathways/` | Pathway (all types) | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/conduits/` | Conduit | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/aerial-spans/` | AerialSpan | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/direct-buried/` | DirectBuried | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/innerducts/` | Innerduct | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/junctions/` | ConduitJunction | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/pathway-locations/` | PathwayLocation | GET, POST, PUT, PATCH, DELETE |
| `/api/plugins/pathways/cable-segments/` | CableSegment | GET, POST, PUT, PATCH, DELETE |

### GeoJSON Endpoints

Read-only GeoJSON FeatureCollection endpoints for GIS clients. See [GeoJSON API](geojson-api.md) for details.

| Endpoint | Geometry | Description |
|----------|----------|-------------|
| `/api/plugins/pathways/geo/structures/` | Point | All structures |
| `/api/plugins/pathways/geo/pathways/` | LineString | All pathway types |
| `/api/plugins/pathways/geo/conduits/` | LineString | Conduits only |
| `/api/plugins/pathways/geo/aerial-spans/` | LineString | Aerial spans only |
| `/api/plugins/pathways/geo/direct-buried/` | LineString | Direct buried only |

## Filtering

All endpoints support filtering via query parameters. Common filters:

```
# Structures by site
GET /api/plugins/pathways/structures/?site_id=1

# Conduits by material
GET /api/plugins/pathways/conduits/?material=hdpe

# Pathways by type
GET /api/plugins/pathways/pathways/?pathway_type=conduit

# Cable segments for a specific cable
GET /api/plugins/pathways/cable-segments/?cable_id=42

# Conduits in a specific bank
GET /api/plugins/pathways/conduits/?conduit_bank_id=5
```

## Example: Create a Structure

```bash
curl -X POST \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "MH-001",
    "structure_type": "manhole",
    "site": 1,
    "location": {
      "type": "Point",
      "coordinates": [-73.5673, 45.5017]
    },
    "elevation": 25.0,
    "owner": "City of Montreal"
  }' \
  https://your-netbox/api/plugins/pathways/structures/
```

## Example: Create a Conduit

```bash
curl -X POST \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "C-001",
    "material": "hdpe",
    "start_structure": 1,
    "end_structure": 2,
    "path": {
      "type": "LineString",
      "coordinates": [[-73.5673, 45.5017], [-73.5700, 45.5030]]
    },
    "inner_diameter": 100,
    "outer_diameter": 110,
    "depth": 1.2,
    "max_cable_count": 4
  }' \
  https://your-netbox/api/plugins/pathways/conduits/
```

## Example: Route a Cable

Create cable segments to define a cable's path through pathways:

```bash
# Segment 1: cable enters conduit C-001
curl -X POST \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cable": 42,
    "pathway": 1,
    "sequence": 1,
    "slack_length": 3.0
  }' \
  https://your-netbox/api/plugins/pathways/cable-segments/

# Segment 2: cable continues through aerial span AS-001
curl -X POST \
  -H "Authorization: Token <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "cable": 42,
    "pathway": 5,
    "sequence": 2,
    "slack_length": 0
  }' \
  https://your-netbox/api/plugins/pathways/cable-segments/
```
