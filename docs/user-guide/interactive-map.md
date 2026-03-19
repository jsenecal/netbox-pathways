# Interactive Map

The interactive map provides a geographic view of your entire cable plant infrastructure, powered by Leaflet with marker clustering and layer controls.

## Accessing the Map

Navigate to **Plugins > Pathways > Map** or visit `/plugins/pathways/map/`.

## Map Features

### Structure Markers

Structures appear as SVG markers with shapes and colors specific to their type:

- **Circles** — Poles, manholes, handholes, splice closures
- **Squares** — Cabinets, vaults, pedestals, equipment rooms, building entrances
- **Diamonds** — Telecom closets, riser rooms
- **Triangles** — Roof mounts
- **Crosshairs** — Towers

Markers cluster when zoomed out and expand as you zoom in.

### Pathway Lines

Pathways render as colored lines connecting structures:

- **Conduit** — Solid brown line
- **Aerial Span** — Dashed blue line
- **Direct Buried** — Dotted gray line
- **Innerduct** — Solid thin orange line

### Layer Toggles

Icon pill toggle buttons at the top of the map control which feature types are visible:

- **Structures** — Toggle structure markers
- **Conduits** — Toggle conduit lines
- **Aerial Spans** — Toggle aerial span lines
- **Direct Buried** — Toggle direct buried lines

External plugin layers (if registered) also appear as toggle buttons.

### Sidebar

Clicking any feature opens a sidebar panel with two views:

**List View:**

- Search field to filter features by name
- Type filter pills to show/hide feature categories
- Scrollable list of all visible features
- Feature count and aggregate statistics

**Detail View:**

- Full feature attributes (name, type, endpoints, dimensions)
- Links to the NetBox detail page
- Related objects (connected pathways, routed cables)

### Hover Popover

Hovering over a feature shows a lightweight popover with the feature name. External layers can configure which fields appear in the popover.

### Cable Trace

The map supports cable trace visualization. From a Cable detail page, the map panel shows the cable's complete physical route highlighted across pathways.

## Controls

| Control | Description |
|---------|-------------|
| Layer toggles | Show/hide feature types |
| Reset View | Zoom to fit all visible features |
| Search | Filter features by name in the sidebar |
| Type filters | Filter sidebar list by feature type |
| Zoom | Standard Leaflet zoom controls |

## URL Parameters

Override default map position via URL:

| Parameter | Example | Description |
|-----------|---------|-------------|
| `lat` | `?lat=40.7128` | Center latitude |
| `lon` | `?lon=-74.0060` | Center longitude |
| `zoom` | `?zoom=15` | Zoom level |
| `bbox` | `?bbox=-74,40,-73,41` | Bounding box (W,S,E,N) |

## External Layers

Other NetBox plugins can register layers on the Pathways map using the [Map Layer Registry](../developer/map-layer-registry.md). External layers appear as additional toggle buttons and render with their configured styling. See the developer guide for registration details.

## Configuration

Default map center and zoom are configured in `PLUGINS_CONFIG`. See [Configuration](../getting-started/configuration.md).
