# Map Layer Registry — Design Spec

External plugins (e.g., netbox-fms) need to display their models on the pathways map. This design introduces a registration system that allows any NetBox plugin to add map layers with styling, sidebar detail panels, and popover tooltips.

## Registration API

Plugins register layers during Django `ready()`:

```python
from netbox_pathways.registry import register_map_layer, LayerStyle, LayerDetail

# URL mode — plugin owns the GeoJSON endpoint
register_map_layer(
    name='fiber_cables',
    label='Fiber Cables',
    geometry_type='LineString',
    source='url',
    url='/api/plugins/fms/geo/fiber-cables/',
    style=LayerStyle(color='#e65100', dash='10 5'),
    detail=LayerDetail(
        url_template='/api/plugins/fms/fiber-cables/{id}/',
        fields=['name', 'cable_type', 'strand_count', 'status'],
    ),
    popover_fields=['name', 'cable_type'],
    default_visible=False,
)

# Reference mode — pathways resolves geometry from FK
register_map_layer(
    name='splice_points',
    label='Splice Points',
    geometry_type='Point',
    source='reference',
    queryset=lambda request: SplicePoint.objects.restrict(request.user, 'view'),
    geometry_field='structure',  # FK to pathways Structure
    style=LayerStyle(
        color_field='splice_type',
        color_map={'fusion': '#2e7d32', 'mechanical': '#f9a825'},
        default_color='#795548',
        icon='mdi-connection',
    ),
    detail=LayerDetail(
        url_template='/api/plugins/fms/splice-points/{id}/',
        fields=['name', 'splice_type', 'status'],
    ),
)
```

## Two Geometry Source Modes

### URL mode

The external plugin provides and owns a GeoJSON endpoint. Pathways fetches it with `?bbox=W,S,E,N&zoom=Z` params. The plugin is responsible for bbox filtering, WGS84 projection, permissions, and returning a standard GeoJSON FeatureCollection.

**Contract:**
- The endpoint MUST accept `bbox` and `zoom` query params and return a GeoJSON FeatureCollection with features in WGS84 (EPSG:4326).
- The endpoint MUST be same-origin (served by the same NetBox instance). Cross-origin endpoints are not supported — the browser sends session cookies automatically for same-origin fetches.
- If using `color_field` categorical styling, the endpoint MUST include that property in GeoJSON feature properties.

### Reference mode

The external plugin's objects don't have their own geometry — they reference a geo-located object via FK (e.g., a splice point at a Structure). Pathways resolves the geometry by joining through the FK.

The plugin provides a callable `queryset(request)` that returns a permission-filtered queryset. Pathways handles geometry resolution, bbox filtering, and result capping.

**Supported FK targets** (defined in `SUPPORTED_GEO_MODELS` mapping):

| FK Target | Geometry Column | Notes |
|---|---|---|
| `netbox_pathways.Structure` | `location` | Always populated (required field) |
| `netbox_pathways.SiteGeometry` | `geometry` | Nullable — rows with null geometry are skipped |

The registry maintains this mapping in a `SUPPORTED_GEO_MODELS` dict:
```python
SUPPORTED_GEO_MODELS = {
    'netbox_pathways.Structure': 'location',
    'netbox_pathways.SiteGeometry': 'geometry',
}
```

Extensible to additional geo models in the future by adding entries.

## Dataclasses

### MapLayerRegistration

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `name` | `str` | yes | — | Unique layer identifier (e.g., `'splice_points'`) |
| `label` | `str` | yes | — | Human-readable label for layer control / sidebar |
| `geometry_type` | `str` | yes | — | `'Point'`, `'LineString'`, or `'Polygon'` |
| `source` | `str` | yes | — | `'url'` or `'reference'` |
| `url` | `str` | URL mode | — | GeoJSON endpoint path (absolute, same-origin) |
| `queryset` | `Callable[[HttpRequest], QuerySet]` | ref mode | — | Returns permission-filtered queryset |
| `geometry_field` | `str` | ref mode | — | FK field name pointing to a supported geo model |
| `feature_fields` | `list[str]` | ref mode | `None` | Fields to include in GeoJSON properties. If `None`, auto-detects scalar fields + FK `__str__` representations. |
| `style` | `LayerStyle` | no | default style | Visual styling configuration |
| `detail` | `LayerDetail` | no | `None` | Sidebar detail panel config. Without it, sidebar shows GeoJSON properties only. |
| `popover_fields` | `list[str]` | no | `['name']` | GeoJSON properties shown on hover. Falls back to `detail.label_field` then feature `id`. |
| `default_visible` | `bool` | no | `False` | Whether layer is on by default |
| `group` | `str` | no | `'External'` | Layer control group heading (use plugin's `verbose_name`) |
| `min_zoom` | `int` | no | `11` | Minimum zoom level to fetch/display this layer |
| `max_zoom` | `int` | no | `None` | Maximum zoom level (no cap by default) |
| `sort_order` | `int` | no | `0` | Controls layer stacking order (higher = rendered on top) |

### LayerStyle

Supports both static (single value) and categorical (per-feature) styling.

| Field | Type | Default | Description |
|---|---|---|---|
| `color` | `str` | `'#795548'` | Static color (hex). Used when `color_field` is not set. |
| `color_field` | `str` | `None` | GeoJSON property name for categorical coloring |
| `color_map` | `dict[str, str]` | `None` | Maps property values to hex colors |
| `default_color` | `str` | `'#795548'` | Fallback color when value not in `color_map` |
| `icon` | `str` | `None` | MDI icon class for point features (e.g., `'mdi-connection'`). Custom SVG shapes are not supported initially — only MDI classes. |
| `dash` | `str` | `None` | SVG dash pattern for lines (e.g., `'10 5'`) |
| `weight` | `int` | `3` | Line weight in pixels |
| `opacity` | `float` | `0.7` | Layer opacity |

**Resolution logic:**
- If `color_field` is set → look up feature property in `color_map`, fall back to `default_color`
- If `color_field` is not set → use `color`

### LayerDetail

| Field | Type | Default | Description |
|---|---|---|---|
| `url_template` | `str` | — | REST API URL with `{id}` placeholder |
| `fields` | `list[str]` | `[]` | Fields from API response to display in sidebar |
| `label_field` | `str` | `'name'` | Field used as the panel title |

## Registry

### Python: `netbox_pathways/registry.py`

`MapLayerRegistry` — singleton dict-like store keyed by layer `name`.

**Validation on registration:**
- No duplicate layer names
- `geometry_type` is one of `Point`, `LineString`, `Polygon`
- `source` is `'url'` or `'reference'`
- URL mode requires `url`; reference mode requires `queryset` and `geometry_field`
- Reference mode: `geometry_field` must be a FK to a supported geo model (checked at first access, not registration time, since models may not be fully loaded during `ready()`)

**Thread safety:** Registration happens during Django startup (single-threaded `ready()` phase). Read access at request time is safe without locking.

**Testing support:** `unregister_map_layer(name)` and `registry.clear()` are provided for test isolation. The registry is module-level and re-populated on process restart, so stale entries from uninstalled plugins are not a concern in production.

## Reference Mode Endpoint

Pathways exposes a generic GeoJSON endpoint for all reference-mode layers:

```
GET /api/plugins/pathways/geo/external/{layer_name}/?bbox=W,S,E,N&zoom=Z
```

**Behavior:**
1. Look up `layer_name` in `MapLayerRegistry`; 404 if not found or not reference mode
2. Call `registration.queryset(request)` to get permission-filtered objects
3. Join through `geometry_field` FK to resolve geometry (ST_Transform to WGS84)
4. Apply bbox filter on resolved geometry
5. Cap at `MAX_GEO_RESULTS` (2000)
6. Serialize as GeoJSON FeatureCollection

**Feature properties:** Controlled by `feature_fields` on the registration:
- If `feature_fields` is provided: only those fields, plus `id`. FK fields are serialized as their `__str__` representation.
- If `feature_fields` is `None`: auto-detect scalar fields (CharField, IntegerField, BooleanField, DateField, etc.) + FK `__str__` representations. Excludes geometry fields, M2M fields, BinaryField, and JSON fields.
- The `color_field` (if using categorical styling) must be included in the feature properties — validated at registration time if `feature_fields` is explicit.

## Data Flow

```
Plugin ready()
  → register_map_layer()
    → MapLayerRegistry (singleton)

Request: GET /plugins/pathways/map/
  → MapView.get_extra_context()
    → reads MapLayerRegistry
    → serializes to PATHWAYS_CONFIG.externalLayers[]
      (name, label, geometry_type, url, style, detail, popover_fields, default_visible, group, min_zoom, max_zoom, sort_order)
    → for reference-mode layers, url is auto-set to /api/plugins/pathways/geo/external/{name}/

JS initializePathwaysMap()
  → reads config.externalLayers[]
  → for each layer:
    1. Create Leaflet layer group
    2. Add toggle to layer control
    3. On bbox change (debounced):
       - Fetch GeoJSON from layer URL (with bbox + zoom params)
       - Apply LayerStyle to each feature
       - Add features to sidebar list
    4. On hover: show popover with popover_fields
    5. On click: fetch detail.url_template, render fields in sidebar panel
```

## JS Changes

No external JS registration mechanism. The TypeScript map code receives `externalLayers` in config and handles them in the same fetch/render loop as native layers.

### Additions to `pathways-map.ts`:
- Generic layer loop driven by `config.externalLayers`
- New `_fetchExternalLayer(layer)` function that fetches from the layer's absolute `url` directly (not through `_fetchGeoJSON` which prepends `API_BASE`). Appends `?format=json&bbox=...&zoom=...` params.
- Per-layer `min_zoom` check: skip fetch if current zoom < layer's `min_zoom`
- `LayerStyle` → Leaflet style options mapping (`color` → stroke/fill, `dash` → `dashArray`, `icon` → marker icon)
- `color_map` lookup at feature render time: read `feature.properties[color_field]`, look up in map, fall back to `default_color`
- External features added to sidebar feature list with their layer label as type
- Layers added to map in `sort_order` sequence (higher values rendered on top)

### Additions to `sidebar.ts`:
- Detail panel fetches `detail.url_template` (replacing `{id}` with feature ID)
- Renders `detail.fields` as label/value pairs
- Layer label used as type filter pill

### Additions to `popover.ts`:
- Reads `popover_fields` from layer config instead of hardcoded name+type
- Falls back to `detail.label_field` (if set), then `'name'`, then feature `id`
- Always appends layer label as the type line

### Additions to `types/`:
- `ExternalLayerConfig` interface matching the JSON shape from Python
- `FeatureType` union widened to `string` to accommodate external layer types (existing native types remain as constants for internal use)

## Layer Control Integration

External layers appear in the layer control alongside native pathways layers. They are grouped by the `group` field (defaults to `'External'`; plugins should set this to their `verbose_name` for clarity). Visibility state is persisted in localStorage with the same `pathways_map_layers` key, keyed by layer name.

## Permissions

- **URL mode:** The external endpoint handles its own authentication and permission filtering. Since endpoints must be same-origin, the browser sends session cookies automatically. No explicit header forwarding needed.
- **Reference mode:** The `queryset` callable receives the request and must return a permission-filtered queryset (via `.restrict(request.user, 'view')` or equivalent).

## Error Handling

- If an external layer's fetch fails (network error, 403, 500), the layer is silently disabled with a console warning. No user-facing error — other layers continue working.
- If a registered layer's plugin is uninstalled, the registry entry is stale. The registry should be cleared on each Django startup (populated fresh during `ready()`).

## Scope Boundaries

**In scope:**
- Python registry with `register_map_layer()` + dataclasses
- Reference-mode GeoJSON endpoint
- JS rendering of external layers (style, sidebar, popover)
- Layer control integration with localStorage persistence

**Out of scope (future):**
- Custom map controls or drawing tools from external plugins
- Clustering configuration for external point layers (uses same defaults as structures)
- Editable features (inline editing from map)
- Legend panel showing all layer styles
