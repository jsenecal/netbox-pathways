# QGIS Integration

NetBox Pathways integrates with QGIS via GeoJSON API endpoints served over HTTP. No direct database access is required — all data flows through authenticated REST API endpoints that respect NetBox permissions.

## Quick Start

The fastest way to get started is with the project generator:

```bash
python manage.py generate_qgis_project \
  --url https://your-netbox \
  --token your-api-token \
  --output pathways.qgs
```

Open `pathways.qgs` in QGIS. All layers are pre-configured.

## Project Generator

The `generate_qgis_project` management command creates a `.qgs` project file with all GeoJSON layers pre-configured.

### Usage

```bash
python manage.py generate_qgis_project --url <base-url> --token <api-token> [--output <file>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--url` | Yes | — | Base URL of your NetBox instance |
| `--token` | Yes | — | NetBox API token |
| `--output` | No | `netbox_pathways.qgs` | Output file path |

### Included Layers

The generated project includes these layers:

| Layer | Geometry | Source Endpoint |
|-------|----------|----------------|
| Structures | Point | `/api/plugins/pathways/geo/structures/` |
| Pathways (All) | LineString | `/api/plugins/pathways/geo/pathways/` |
| Conduits | LineString | `/api/plugins/pathways/geo/conduits/` |
| Aerial Spans | LineString | `/api/plugins/pathways/geo/aerial-spans/` |
| Direct Buried | LineString | `/api/plugins/pathways/geo/direct-buried/` |

All layers use EPSG:4326 (WGS84) projection and authenticate via the API token.

## Style Files

QGIS style files (`.qml`) are included with the plugin for consistent cartographic rendering:

| File | Layer | Description |
|------|-------|-------------|
| `structures.qml` | Structures | Categorized by structure type — different shape and color per type |
| `pathways.qml` | Pathways | Categorized by pathway type — different color and line style per type |

### Loading Styles

1. Right-click a layer in QGIS → **Properties**
2. Go to the **Symbology** tab
3. Click **Style** → **Load Style**
4. Select the `.qml` file

Style files are located in the plugin's static directory:

```
netbox_pathways/static/netbox_pathways/qgis/structures.qml
netbox_pathways/static/netbox_pathways/qgis/pathways.qml
```

After installation, they're available at:

```
<netbox-static>/netbox_pathways/qgis/structures.qml
<netbox-static>/netbox_pathways/qgis/pathways.qml
```

### Structure Symbology

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

### Pathway Symbology

| Type | Line Style | Color |
|------|-----------|-------|
| Conduit | Solid | Brown |
| Aerial | Dash | Blue |
| Direct Buried | Dot | Gray |
| Innerduct | Solid | Orange |
| Cable Tray | Solid | Green |
| Raceway | Solid | Indigo |

## Manual Layer Setup

If you prefer to add layers manually instead of using the project generator:

1. **Layer → Add Layer → Add Vector Layer**
2. Set source type to **Protocol: HTTP(S)**
3. Enter the endpoint URI with `?format=json&limit=0` appended
4. Add an HTTP Authorization header with your token

Example URI for structures:

```
https://your-netbox/api/plugins/pathways/geo/structures/?format=json&limit=0
```

Authorization header:

```
Token your-api-token
```

## Print Layouts

QGIS print layouts can be created manually for your specific map extents and paper sizes. Common layouts for cable plant documentation:

- **Overview map** — All structures and pathways in a region
- **Route map** — A specific cable route highlighted
- **Detail map** — Close-up of a structure or junction with conduit banks labeled

These are standard QGIS functionality — see the [QGIS Print Layout documentation](https://docs.qgis.org/latest/en/docs/user_manual/print_composer/index.html).
