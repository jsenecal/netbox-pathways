# HTML Fragment Detail Cards for External Map Layers

**Status:** Approved

## Problem

The map sidebar detail panel for external layers currently fetches JSON from a REST API and renders flat key-value field tables. This is insufficient for plugins that need to display rich, domain-specific content — for example, a fiber management plugin showing colored fiber tube diagrams, splice schematics, or cable cross-sections.

## Solution

Add an optional `detail_url` field to `LayerDetail` that points to an HTML fragment endpoint owned by the external plugin. When present, the sidebar fetches the HTML and injects it directly instead of rendering a field table.

## Registry Changes

### `LayerDetail` dataclass

Add `detail_url` alongside the existing `url_template`:

```python
@dataclass(frozen=True)
class LayerDetail:
    url_template: str | None = None    # Object detail page URL (for "View" link)
    detail_url: str | None = None      # HTML fragment endpoint (new)
    fields: list[str] = field(default_factory=list)
    label_field: str = 'name'
```

- `url_template` — Existing field. Used to build the "View" link to the object's detail page and as a JSON API fallback for field rendering.
- `detail_url` — New field. URL pattern with `{id}` placeholder. Returns an HTML fragment for the sidebar detail panel.
- `fields` — Existing field. Used for JSON-mode field rendering (fallback when `detail_url` is absent).

### `to_json()` serialization

`detail_url` serializes to `detailUrl` in the camelCase JSON config sent to the frontend.

### Registration example

```python
register_map_layer(
    name='fiber-cables',
    label='Fiber Cables',
    geometry_type='LineString',
    source='reference',
    queryset=lambda r: FiberCable.objects.all(),
    geometry_field='site',
    feature_fields=['name', 'cable_type', 'fiber_count'],
    style=LayerStyle(color='#e91e63'),
    detail=LayerDetail(
        url_template='/plugins/netbox-fms/fiber-cables/{id}/',
        detail_url='/api/plugins/netbox-fms/fiber-cables/{id}/card/',
        fields=['name', 'cable_type', 'fiber_count'],
    ),
)
```

## TypeScript Changes

### `ExternalLayerDetail` interface

Add `detailUrl?: string` to the existing interface in `types/external.ts`.

### Sidebar fetch logic (`sidebar.ts`)

Modify `_fetchDetail()` with a three-tier resolution:

1. **If `extCfg.detail.detailUrl` exists** — fetch with `Accept: text/html`, inject `response.text()` via `innerHTML`.
2. **If `extCfg.detail.urlTemplate` exists** (no `detailUrl`) — existing JSON fetch + field table rendering.
3. **Neither exists** — render raw GeoJSON properties as key-value table (existing fallback).

The fetch uses the same session cookie / CSRF pattern as existing fetches. No new authentication mechanism needed.

### Caching

HTML responses are cached in `_detailCache` by feature ID, same as JSON responses. The cache value is a string (HTML) instead of an object. `_fetchDetail` distinguishes by checking whether `detailUrl` was used.

## Plugin-Side Contract

The HTML fragment endpoint must:

- Return a self-contained HTML fragment (no `<html>`, `<head>`, `<body>` wrappers).
- Use Tabler/NetBox CSS variables for theme compatibility (colors, fonts, spacing).
- Be accessible with session authentication (same-origin request, CSRF cookie included automatically).
- Return appropriate HTTP status codes (200 for success, 404 if object not found).

Example response:

```html
<div class="fms-cable-card">
  <div class="fw-bold">NV01:04-DR11:04 (split)</div>
  <div class="text-muted">OS2 · 24F</div>
  <div class="fms-fiber-grid" style="margin-top: 8px;">
    <span class="fms-fiber" style="background: #e53935;"></span>
    <span class="fms-fiber" style="background: #43a047;"></span>
    <!-- ... more fiber dots ... -->
  </div>
  <div class="text-muted mt-1" style="font-size: 0.8em;">2 tubes × 12F</div>
</div>
```

## Security

Using `innerHTML` with plugin-served HTML follows the same trust model as NetBox's `PluginTemplateExtension` system — installed plugins are trusted code running in the same Django instance. No arbitrary external HTML is loaded; only endpoints registered by installed plugins.

## Scope

### In scope
- `detail_url` field on `LayerDetail`
- Sidebar HTML fragment injection
- Cache support for HTML responses

### Out of scope
- Popover changes (remains minimal text-only with `popoverFields`)
- "Show on global map" button (separate effort)
- Styling of plugin HTML fragments (plugin's responsibility)
