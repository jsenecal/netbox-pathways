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

- **Structures** -- Toggle structure markers
- **Conduits** -- Toggle conduit lines
- **Aerial Spans** -- Toggle aerial span lines
- **Direct Buried** -- Toggle direct buried lines

External plugin layers (if registered) also appear as toggle buttons.

### Layer Density Gating

The map keeps the display readable by checking how many features each enabled layer would draw inside the current viewport. Every pan or zoom hits a lightweight `/api/plugins/pathways/geo/info/` endpoint that returns counts and thresholds; the frontend then decides per layer whether to draw it directly, draw it with client-side clustering, or hide it entirely. Hidden layer toggles dim to roughly half-opacity and show the in-view count beside the label so it is obvious why the layer is not on screen -- usually zooming in is enough to bring it back.

Defaults (override in `PLUGINS_CONFIG['netbox_pathways']['map_thresholds']`):

| Layer | Below `cluster` (structures only) | Above `cluster` | Above `hide` |
| --- | --- | --- | --- |
| Structures (`cluster: 200`, `hide: 5000`) | individual markers | client-side clusters | server-side clusters; all support layers hidden |
| Conduit Banks (`hide: 500`) | rendered | -- | hidden, count shown on toggle |
| Conduits / Aerial Spans / Direct Buried / Circuits (`hide: 500`) | rendered | -- | hidden, count shown on toggle |

When the structures layer crosses either threshold (client cluster or server cluster), the supporting infrastructure layers are suppressed regardless of their own counts: at that density a single highlighted line cannot be matched back to a clustered structure marker, so the whole set is hidden until you zoom in. Reference-mode external layers participate in the same gating, using their `max_features` registration value (default 500).

### How the gating performs during panning

To keep the gating logic from making the map feel laggy, the frontend uses three zoom bands:

| Zoom band | Behaviour | `/info` round-trip |
| --- | --- | --- |
| Below `MIN_DATA_ZOOM` (11) | Nothing renders | None |
| `MIN_DATA_ZOOM` to `map_skip_info_zoom` -- 1 (default 16) | Render from the most recent cached `/info` immediately; `/info` revalidates in the background with `If-None-Match`. A 304 leaves the screen untouched; a 200 only triggers a reconcile if the per-layer decision actually changes. First load with an empty cache still waits one round-trip. | Conditional, in the background |
| At or above `map_skip_info_zoom` (default 17) | Render every enabled layer directly. The viewport is too small to plausibly cross any hide/cluster threshold, so the gate is skipped. | None |

Set `PLUGINS_CONFIG['netbox_pathways']['map_skip_info_zoom']` to raise or lower the skip-info threshold for deployments with unusual feature density.

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
