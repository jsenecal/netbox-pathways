# GeoJSON API Reference

Read-only GeoJSON endpoints for GIS client consumption. All endpoints require authentication and return standard GeoJSON FeatureCollections.

## Endpoints

| Endpoint | Geometry | Description |
|----------|----------|-------------|
| `GET /api/plugins/pathways/geo/structures/` | Point | All structures |
| `GET /api/plugins/pathways/geo/pathways/` | LineString | Every pathway type; filter with `?pathway_type=` |
| `GET /api/plugins/pathways/geo/circuits/` | LineString | Circuit geometries |
| `GET /api/plugins/pathways/geo/info/` | -- | Per-layer feature counts and thresholds for the map |
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
| `site_name` | string | Site name |

### Pathways

The feature geometry is the pathway's own `geometry`. Pathways without one
(indoor pathways, and children that follow their parent's route) are left
out. Properties:

| Property | Type | Description |
|----------|------|-------------|
| `id` | integer | Pathway ID |
| `label` | string | Pathway label |
| `pathway_type` | string | Type identifier (`conduit_bank`, `conduit`, `aerial`, ...) |
| `geo_length` | float | Drawn length in meters |
| `start_anchor` / `end_anchor` | integer | Structure each end belongs to |
| `search_match` | string | With `?q=`: label of the child the search matched through, or null when the pathway matched itself |

Type-specific attributes (material, aerial type, ...) are not in the GeoJSON
properties; read them from `/api/plugins/pathways/pathways/<id>/`.

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

### Excluding Statuses

Hide features by lifecycle status. Accepts a comma-separated list or a
repeated parameter; unknown values are ignored. Applies to the structure and
pathway layers and to `/info` counts (circuit geometries carry no plugin
status and are unaffected):

```
?exclude_status=retired,abandoned
?exclude_status=retired&exclude_status=abandoned
```

The `/info` response also carries the available status choices for building
filter UIs:

```json
"statuses": [
  {"value": "active", "label": "Active", "color": "green"},
  ...
]
```

### Map Containers

`geo/pathways/` returns every pathway that has its own geometry. `?containers=true`
keeps only the pathways the map draws: top-level pathways of a drawn type
(conduit bank, conduit, aerial span, direct buried, submarine).
`?containers=false` keeps everything else. The map requests one layer per
drawn type:

```
/api/plugins/pathways/geo/pathways/?pathway_type=conduit_bank&containers=true
```

### Search

`?q=` on `geo/pathways/` matches a pathway on its own fields, or through any
descendant the user may view that matches; the matching descendant's label is
returned in `search_match`.

### Standard Filters

All standard model filters are supported:

```
?site_id=1
?structure_type=manhole
?pathway_type=conduit&material=pvc
?parent_id=12
?ancestor_id=12
```

## Result Limits

GeoJSON responses are capped at **2000 features** per request to prevent performance issues. Use bounding box filtering for dense areas.

## CORS

GeoJSON endpoints follow NetBox's CORS configuration. For QGIS or other desktop GIS clients, ensure your NetBox instance allows the necessary origins or use token authentication directly.
