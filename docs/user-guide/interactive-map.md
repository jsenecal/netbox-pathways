# Interactive Map

The interactive map provides a geographic view of your entire cable plant infrastructure, powered by Leaflet with marker clustering and layer controls.

## Accessing the Map

Navigate to **Plugins > Pathways > Map** or visit `/plugins/pathways/map/`.

## Map Features

### Structure Markers

Structures appear as SVG markers with shapes and colors specific to their type:

- **Circles** -- Poles, manholes, handholes
- **Squares** -- Cabinets, vaults, pedestals, equipment rooms, building entrances
- **Diamonds** -- Telecom closets, riser rooms
- **Triangles** -- Roof mounts
- **Crosshairs** -- Towers

Markers cluster when zoomed out and expand as you zoom in.

### What the map draws

The map draws only **containers**: pathways of a drawn type that have no
parent. Each drawn type has its own layer and line style:

| Type | Line style | Color |
|------|------------|-------|
| Conduit Bank | Solid, wide | Magenta (`#ad1457`) |
| Conduit (top-level only) | Dashed `5 5` | Orange (`#f57c00`) |
| Aerial Span | Dashed `10 5` | Blue (`#1565c0`) |
| Direct Buried | Dotted `2 4` | Gray (`#616161`) |
| Submarine | Dash-dot `6 2 2 2` | Navy (`#1a237e`) |

Innerducts, cable trays, raceways and any pathway with a parent (a conduit in
a bank or a raceway) are never drawn. The legend lists exactly the drawn
types.

A pathway that is not drawn is represented by its **map container**: the
outermost drawn pathway among itself and its ancestors. An innerduct in a
conduit in a bank resolves to the bank; an innerduct in a top-level
direct buried pathway resolves to that pathway. A pathway with no drawn
ancestor-or-self (a conduit or tray in a raceway) has no map container.

- The **Map** button on a pathway's detail page and in pathway tables opens
  the map on its container; when there is none, the map opens with nothing
  selected.
- `?select=<type>-<id>` (for example `?select=innerduct-42`) selects the
  container. Nothing is selected when there is no container, or when the user
  may not view the pathway or its container.
- **Map search** matches a container when it or anything inside it matches.
  A container found through a child is listed as `Bank A (via Duct 3)`. Only
  children the user may view are searched, so the search never reveals a
  pathway the user cannot see.

### Layer Toggles

Icon pill toggle buttons at the top of the map control which feature types are visible:

- **Structures** -- Toggle structure markers
- **Conduit Banks** -- Toggle conduit bank lines
- **Conduits** -- Toggle top-level conduit lines
- **Aerial Spans** -- Toggle aerial span lines
- **Direct Buried** -- Toggle direct buried lines
- **Submarine** -- Toggle submarine lines
- **Circuit Routes** -- Toggle circuit routes

External plugin layers (if registered) also appear as toggle buttons.

### Hiding Inactive Infrastructure

Below the layer toggles, the **Hide inactive** button removes features whose
lifecycle status you consider inactive from every layer. The gear button next
to it opens a small panel with one checkbox per status choice, defining the
"inactive" set; the default is `Retired` + `Abandoned in place`. Both the
toggle and the set persist per browser (localStorage), so the map remembers
your preference across visits.

Filtering happens server-side: the layer requests and the `/info` count
endpoint both receive the exclusion, so viewport counts, clustering
thresholds, and what is actually drawn always agree. Circuit routes are not
affected -- circuits carry NetBox core statuses, not plugin pathway statuses.

### Hiding Unoccupied Infrastructure

The **Hide unoccupied** button below it filters the map down to plant that
actually carries cable: pathways with at least one routed cable segment and
the structures that terminate them. Occupancy is containment-aware -- a
conduit whose innerduct carries a cable and a conduit bank with an occupied
member conduit both stay visible. The toggle persists per browser, filters
server-side like the status exclusion (so counts and clusters agree with
what is drawn), and composes with **Hide inactive**. Circuit routes and
junctions are unaffected.

### Layer Density Gating

The map keeps the display readable by checking how many features each enabled layer would draw inside the current viewport. Every pan or zoom hits a lightweight `/api/plugins/pathways/geo/info/` endpoint that returns counts and thresholds; the frontend then decides per layer whether to draw it directly, draw it with client-side clustering, or hide it entirely. Hidden layer toggles dim to roughly half-opacity and show the in-view count beside the label so it is obvious why the layer is not on screen -- usually zooming in is enough to bring it back.

Defaults (override in `PLUGINS_CONFIG['netbox_pathways']['map_thresholds']`):

| Layer | Below `cluster` (structures only) | Above `cluster` | Above `hide` |
| --- | --- | --- | --- |
| Structures (`cluster: 200`, `hide: 5000`) | individual markers | client-side clusters | server-side clusters; all support layers hidden |
| Conduit Banks (`hide: 500`) | rendered | -- | hidden, count shown on toggle |
| Conduits / Aerial Spans / Direct Buried / Submarine / Circuits (`hide: 500`) | rendered | -- | hidden, count shown on toggle |

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

- Full feature attributes (name, status, type, endpoints, dimensions) --
  the lifecycle status renders as a colored badge matching the list views
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
| `select` | `?select=conduit-17` | Select a feature (`structure-<id>` or `<pathway_type>-<id>`); a pathway selects its map container |

## Map Panels on Detail Pages

Besides the full-page map, a read-only map panel is injected into detail
pages so infrastructure is visible in context:

| Page | What the panel shows |
|------|----------------------|
| Structure, Pathway (every type), Conduit Junction | The object's own geometry, plus endpoint structures for pathways |
| Site | The site boundary from [Site Geometry](site-geometry.md), every structure assigned to the site, and pathways with an endpoint structure at the site |
| Location | Every structure in the location, plus pathways starting or ending at it with their far-end structures |

The Location panel walks the location tree: viewing a parent shows the
structures and pathways of its child locations too, matching how NetBox counts
related objects on the same page. Each structure is drawn once even when
several pathways share it as an endpoint.

Markers shown only for context are drawn faded -- on a Location page that means
the far-end structure of a pathway leaving the location, so the location's own
structures read first. A structure that is both in the location and a pathway
endpoint is drawn at full strength.

Indoor pathways that run location-to-location carry no geographic path, so they
contribute nothing to the map -- they appear in the Pathways tables instead.

## External Layers

Other NetBox plugins can register layers on the Pathways map using the [Map Layer Registry](../developer/map-layer-registry.md). External layers appear as additional toggle buttons and render with their configured styling. See the developer guide for registration details.

## Configuration

Default map center and zoom are configured in `PLUGINS_CONFIG`. See [Configuration](../getting-started/configuration.md).
