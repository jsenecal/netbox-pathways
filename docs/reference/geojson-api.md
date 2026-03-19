# GeoJSON API Reference

Read-only GeoJSON endpoints for GIS client consumption. All endpoints require authentication and return standard GeoJSON FeatureCollections.

## Endpoints

| Endpoint | Geometry | Description |
|----------|----------|-------------|
| `GET /api/plugins/pathways/geo/structures/` | Point | All structures |
| `GET /api/plugins/pathways/geo/pathways/` | LineString | All pathways |
| `GET /api/plugins/pathways/geo/conduits/` | LineString | Conduits only |
| `GET /api/plugins/pathways/geo/aerial-spans/` | LineString | Aerial spans only |
| `GET /api/plugins/pathways/geo/direct-buried/` | LineString | Direct buried only |
| `GET /api/plugins/pathways/geo/external/<name>/` | Varies | External plugin layer |

## Authentication

Same token-based authentication as the standard NetBox API:

```
Authorization: Token your-api-token
```

## Response Format

All endpoints return GeoJSON FeatureCollections:

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
        "site": "Main Campus"
      }
    }
  ]
}
```

## Properties by Layer

### Structures

| Property | Type | Description |
|----------|------|-------------|
| `id` | integer | Structure ID |
| `name` | string | Structure name |
| `structure_type` | string | Type identifier |
| `site` | string | Site name |
| `elevation` | float | Elevation in meters |
| `installation_date` | string | ISO date |

### Pathways

| Property | Type | Description |
|----------|------|-------------|
| `id` | integer | Pathway ID |
| `name` | string | Pathway name |
| `pathway_type` | string | Type identifier |
| `start_structure` | string | Start structure name |
| `end_structure` | string | End structure name |
| `length` | float | Length in meters |

### Conduits

Includes all Pathway properties plus:

| Property | Type | Description |
|----------|------|-------------|
| `material` | string | Conduit material |
| `inner_diameter` | float | Inner diameter (mm) |
| `outer_diameter` | float | Outer diameter (mm) |
| `depth` | float | Burial depth (m) |

### External Layers (Reference Mode)

Properties depend on the layer's `feature_fields` configuration. At minimum:

| Property | Type | Description |
|----------|------|-------------|
| `id` | integer | Object primary key |

If `feature_fields` is not specified, all scalar fields and FK display values are included automatically. Binary, JSON, and geometry fields are excluded.

## Query Parameters

### Bounding Box

Filter features within a geographic bounding box:

```
?bbox=W,S,E,N
```

Example: `?bbox=-74.0,40.7,-73.9,40.8`

### Format

```
?format=json
```

### Zoom Level

Passed to external layers for zoom-dependent behavior:

```
?zoom=15
```

### Standard Filters

All standard model filters are supported:

```
?site_id=1
?structure_type=manhole
?material=pvc
```

## Result Limits

GeoJSON responses are capped at **2000 features** per request to prevent performance issues. Use bounding box filtering for dense areas.

## CORS

GeoJSON endpoints follow NetBox's CORS configuration. For QGIS or other desktop GIS clients, ensure your NetBox instance allows the necessary origins or use token authentication directly.
