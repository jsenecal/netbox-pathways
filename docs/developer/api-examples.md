# API Examples

All API endpoints are under `/api/plugins/pathways/`. Authentication uses NetBox API tokens passed via the `Authorization` header.

## Authentication

```bash
export TOKEN="your-netbox-api-token"
export NETBOX="https://netbox.example.com"

curl -H "Authorization: Token $TOKEN" \
     -H "Accept: application/json" \
     "$NETBOX/api/plugins/pathways/structures/"
```

## Structures

### List Structures

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/structures/"
```

### Filter by Site

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/structures/?site_id=1"
```

### Filter by Type

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/structures/?structure_type=manhole"
```

### Create a Structure

```bash
curl -X POST \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "MH-042",
       "structure_type": "manhole",
       "site": 1,
       "location": 3,
       "geometry": "POINT(-73.5 45.5)"
     }' \
     "$NETBOX/api/plugins/pathways/structures/"
```

## Pathways

Every pathway type is served by one endpoint, `/api/plugins/pathways/pathways/`.
`pathway_type` is required on create; `parent` places a pathway inside
another one, subject to the containment rule (see
[Pathways](../user-guide/pathways.md#hierarchy)).

### List Conduits

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/pathways/?pathway_type=conduit"
```

### Filter by Material

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/pathways/?pathway_type=conduit&material=pvc"
```

### Create a Conduit Bank and a Conduit in It

```bash
curl -X POST \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "pathway_type": "conduit_bank",
       "label": "DB-101",
       "start_structure": 1,
       "end_structure": 2,
       "geometry": "LINESTRING(-73.5 45.5, -73.4 45.6)",
       "configuration": "2x3",
       "total_conduits": 6
     }' \
     "$NETBOX/api/plugins/pathways/pathways/"

# The conduit follows the bank's route and inherits its endpoints
curl -X POST \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "pathway_type": "conduit",
       "label": "C-101",
       "parent": 10,
       "position": "A1",
       "material": "pvc",
       "inner_diameter": 100
     }' \
     "$NETBOX/api/plugins/pathways/pathways/"
```

### Everything Inside a Pathway

```bash
# Direct children
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/pathways/?parent_id=10"

# Every descendant, at any depth
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/pathways/?ancestor_id=10"
```

Deleting a pathway that still has children returns `409 Conflict`; delete or
reassign the children first.

## Cable Segments

### Route a Cable

Create ordered segments to route a cable through pathways:

```bash
# Segment 1
curl -X POST \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "cable": 42,
       "pathway": 1,
       "sequence": 1,
       "slack_length": 3.0
     }' \
     "$NETBOX/api/plugins/pathways/cable-segments/"

# Segment 2
curl -X POST \
     -H "Authorization: Token $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "cable": 42,
       "pathway": 5,
       "sequence": 2,
       "slack_length": 0
     }' \
     "$NETBOX/api/plugins/pathways/cable-segments/"
```

### Get Cable Route (Pull Sheet Data)

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/cable-segments/?cable_id=42&ordering=sequence"
```

## GeoJSON

### Get Structures as GeoJSON

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/geo/structures/?format=json"
```

Response:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-73.5, 45.5]
      },
      "properties": {
        "id": 1,
        "name": "MH-042",
        "structure_type": "manhole",
        "site": "Main Campus"
      }
    }
  ]
}
```

### Bounding Box Filter

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/geo/structures/?bbox=-74,40,-73,41"
```

### External Layer GeoJSON (Reference Mode)

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/geo/external/fiber-cables/?format=json&bbox=-74,40,-73,41"
```

## Traversal

### Find Routes Between Structures

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/traversal/routes/?from=1&to=5"
```

### Trace a Cable

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/traversal/cable-trace/?cable_id=42"
```

### Get Neighbors

```bash
curl -H "Authorization: Token $TOKEN" \
     "$NETBOX/api/plugins/pathways/traversal/neighbors/?structure_id=1"
```

## Python Client Example

```python
import requests

NETBOX_URL = "https://netbox.example.com"
TOKEN = "your-api-token"
HEADERS = {
    "Authorization": f"Token {TOKEN}",
    "Content-Type": "application/json",
}

# List all structures
resp = requests.get(
    f"{NETBOX_URL}/api/plugins/pathways/structures/",
    headers=HEADERS,
)
structures = resp.json()["results"]

# Get GeoJSON for QGIS or other GIS tools
resp = requests.get(
    f"{NETBOX_URL}/api/plugins/pathways/geo/structures/",
    headers=HEADERS,
    params={"format": "json"},
)
geojson = resp.json()

# Get pull sheet data for a cable
resp = requests.get(
    f"{NETBOX_URL}/api/plugins/pathways/cable-segments/",
    headers=HEADERS,
    params={"cable_id": 42, "ordering": "sequence"},
)
route = resp.json()["results"]
```
