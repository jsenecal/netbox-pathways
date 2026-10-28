# QGIS Integration

NetBox Pathways provides a GeoJSON REST API and QGIS tooling for full GIS client integration. No direct database access is required -- all spatial data is served through authenticated API endpoints that respect NetBox permissions.

## Quick Start

Generate a pre-configured QGIS project file:

```bash
python manage.py generate_qgis_project \
    --url https://netbox.example.com \
    --token your-api-token-here
```

This creates a `.qgs` file with all Pathways layers pre-configured, including authentication and symbology.

## Available Layers

The generated project includes these GeoJSON layers:

| Layer | Geometry | Endpoint |
|-------|----------|----------|
| Structures | Point | `/api/plugins/pathways/geo/structures/` |
| Pathways (All) | LineString | `/api/plugins/pathways/geo/pathways/` |
| Conduit Bank | LineString | `/api/plugins/pathways/geo/pathways/?pathway_type=conduit_bank&containers=true` |
| Conduit | LineString | `/api/plugins/pathways/geo/pathways/?pathway_type=conduit&containers=true` |
| Aerial Span | LineString | `/api/plugins/pathways/geo/pathways/?pathway_type=aerial&containers=true` |
| Direct Buried | LineString | `/api/plugins/pathways/geo/pathways/?pathway_type=direct_buried&containers=true` |
| Submarine | LineString | `/api/plugins/pathways/geo/pathways/?pathway_type=submarine&containers=true` |

Like the web map, the per-type layers hold map containers only (top-level
pathways of a drawn type), so a conduit in a bank is drawn once, as its bank.
"Pathways (All)" holds every pathway that has its own geometry.

## Layer Symbology

### Structure Symbols

| Type | Shape | Color |
|------|-------|-------|
| Pole | Circle | Green |
| Manhole | Square | Blue |
| Handhole | Diamond | Cyan |
| Cabinet | Square | Orange |
| Building Entrance | Triangle | Crimson |
| Equipment Room | Square | Purple |
| Telecom Closet | Diamond | Steel Blue |
| Riser Room | Triangle | Brown |

### Pathway Symbols

| Type | Line Style | Color |
|------|------------|-------|
| Conduit | Solid | Brown |
| Aerial | Dashed | Blue |
| Direct Buried | Dotted | Gray |
| Innerduct | Solid | Orange |
| Cable Tray | Solid | Green |
| Raceway | Solid | Indigo |
| Other (conduit bank, submarine, blank) | Dashed (thin) | Gray |

## Style Files

Pre-made QGIS style files (`.qml`) are included with the plugin:

```
static/netbox_pathways/qgis/
├── structures.qml
└── pathways.qml
```

To apply styles manually: **Layer Properties > Style > Load Style**, then select the `.qml` file.

## Manual Layer Setup

To add layers without the project generator:

1. Open QGIS
2. **Layer > Add Layer > Add Vector Layer**
3. Set source type to **Protocol: HTTP(S)**
4. Enter the URL: `https://netbox.example.com/api/plugins/pathways/geo/structures/?format=json`
5. Under **Authentication**, configure an HTTP header:
    - Header: `Authorization`
    - Value: `Token your-api-token-here`
6. Click **Add**

Repeat for each layer endpoint.

## Filtering

All GeoJSON endpoints support query parameter filtering:

```
# Structures at a specific site
/api/plugins/pathways/geo/structures/?site_id=1

# Conduits of a specific material
/api/plugins/pathways/geo/pathways/?pathway_type=conduit&material=pvc

# Features within a bounding box
/api/plugins/pathways/geo/structures/?bbox=-74,40,-73,41
```

## Print Layouts

QGIS print layouts can be used to create custom maps:

1. Open the generated project
2. **Project > New Print Layout**
3. Add a map item showing your desired extent
4. Add legends, scale bars, titles as needed
5. Export to PDF or image

!!! tip
    The GeoJSON API is read-only. Edits must be made through the NetBox web interface or REST API. QGIS is a visualization and analysis tool for Pathways data.
