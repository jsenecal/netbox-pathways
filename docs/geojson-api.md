# GeoJSON API

NetBox Pathways provides read-only GeoJSON endpoints designed for consumption by QGIS, Leaflet, MapLibre, and other GIS clients. These endpoints return standard [GeoJSON FeatureCollections](https://datatracker.ietf.org/doc/html/rfc7946) and respect NetBox's authentication and permissions.

## Endpoints

| Endpoint | Geometry | Description |
|----------|----------|-------------|
| `/api/plugins/pathways/geo/structures/` | Point | Structures with type, site, owner |
| `/api/plugins/pathways/geo/pathways/` | LineString | All pathway types unified |
| `/api/plugins/pathways/geo/conduits/` | LineString | Conduits with material, bank info |
| `/api/plugins/pathways/geo/aerial-spans/` | LineString | Aerial spans with attachment details |
| `/api/plugins/pathways/geo/direct-buried/` | LineString | Direct buried with depth, tape, wire |

All endpoints are **read-only** (GET only) and support the same filtering as the standard REST API endpoints.

## Response Format

Each endpoint returns a GeoJSON FeatureCollection:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-73.5673, 45.5017]
      },
      "properties": {
        "id": 1,
        "name": "MH-001",
        "structure_type": "manhole",
        "structure_type_display": "Manhole",
        "site": 1,
        "site_name": "Downtown",
        "elevation": 25.0,
        "owner": "City of Montreal",
        "installation_date": "2020-06-15"
      }
    }
  ]
}
```

## Properties

### Structures

| Property | Description |
|----------|-------------|
| `name` | Structure name |
| `structure_type` | Type code |
| `structure_type_display` | Human-readable type |
| `site` | Site ID |
| `site_name` | Site name |
| `elevation` | Elevation in meters |
| `owner` | Owner/operator |
| `installation_date` | Installation date |

### Pathways

| Property | Description |
|----------|-------------|
| `name` | Pathway name |
| `pathway_type` | Type code |
| `pathway_type_display` | Human-readable type |
| `start_name` | Start endpoint name (structure or location) |
| `end_name` | End endpoint name |
| `length` | Length in meters |
| `cable_count` | Current cables |
| `max_cable_count` | Maximum capacity |
| `utilization_pct` | Utilization percentage |
| `installation_date` | Installation date |

### Conduits

All pathway properties plus:

| Property | Description |
|----------|-------------|
| `material` / `material_display` | Conduit material |
| `inner_diameter` | Inner diameter (mm) |
| `outer_diameter` | Outer diameter (mm) |
| `depth` | Burial depth (m) |
| `conduit_bank` / `conduit_bank_name` | Associated bank |
| `bank_position` | Position in bank |

## Authentication

GeoJSON endpoints use the same NetBox token authentication:

```bash
curl -H "Authorization: Token <your-token>" \
  https://your-netbox/api/plugins/pathways/geo/structures/
```

## QGIS Connection

To use these endpoints in QGIS:

1. **Layer > Add Layer > Add Vector Layer**
2. Source type: **Protocol: HTTP(S)**
3. URI: `https://your-netbox/api/plugins/pathways/geo/structures/?format=json&limit=0`
4. Under **Authentication**, add an HTTP header:
   - Key: `Authorization`
   - Value: `Token <your-api-token>`

Or use the [QGIS project generator](qgis.md#project-generator) to create a pre-configured project file.

## Filtering

GeoJSON endpoints support the same query parameters as the standard API:

```
# Structures in a specific site
/api/plugins/pathways/geo/structures/?site_id=1

# Conduits by material
/api/plugins/pathways/geo/conduits/?material=hdpe

# Aerial spans by type
/api/plugins/pathways/geo/aerial-spans/?aerial_type=adss
```
