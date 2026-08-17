# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`split_pathway` management command.** Splits a pathway at the structures
  it passes into per-hop pathways, with PostGIS candidate detection,
  dry-run preview, containment cascade (conduit banks and innerducts),
  cable segment re-routing, and optional change logging via --user.
  Refs #87.

- **Add-child buttons that inherit the parent's attributes.** The Conduits
  panel on a conduit bank and the Innerducts panel on a conduit now carry
  an "Add" button that opens the create form pre-filled from the parent:
  endpoints and faces for bank conduits (plus installed-by and dates),
  endpoints for innerducts. Blank endpoints on a bank conduit now inherit
  from the bank at save time, matching the existing innerduct behavior,
  and contained pathways (bank conduits, innerducts) no longer require or
  synthesize their own path geometry -- the parent owns the route. Tenant
  columns on the conduit and innerduct tables fall back to the parent
  chain's tenant, marked with `*` in the NetBox style.
  Requested by @marcusyuri. Refs #77.

- **Hide unoccupied toggle on the interactive map.** A new sidebar button
  under Hide inactive filters every layer down to plant that carries cable:
  pathways with at least one routed segment and the structures terminating
  them. Filtering is server-side, so viewport counts, cluster totals, and
  drawn features always agree, and the preference persists per browser.
  The `occupied` filter now also exists on the Conduit, Aerial Span, Direct
  Buried, Innerduct, and Conduit Bank filter sets (list views and REST API
  included) and is containment-aware: a conduit hosting an occupied
  innerduct, and a bank holding an occupied member conduit, count as
  occupied. Refs #112.

- **Full-screen toggle on the geometry edit widget.** A new button in the
  map's top-right corner grows it to fill the browser window, so tracing a
  route with many intermediate vertices no longer means repeatedly zooming
  and panning inside a 400px box. Escape or a second click returns to the
  inline size. The geometry stays in the form field throughout, so nothing
  is saved, lost or reloaded on the way in or out.
  Requested by @marcusyuri. Refs #75.

- **Polygon structures draw their real footprint.** A structure whose
  geometry is a polygon now renders as a filled outline in its structure-type
  color -- on the interactive map, on its own detail page and on the Site /
  Location map panels -- instead of a marker dropped at the centroid. Below
  `map_structure_polygon_zoom` (new setting, default `18`) the footprint
  collapses back to the type icon at the centroid, since an outline that small
  is a sub-pixel smudge on a wide view. Detail pages open zoomed in far enough
  to show the outline of the structure they are about. Refs #96.

- **`Structure.location`** -- an optional FK to `dcim.Location`, recording
  which location inside the site a structure sits in. Validated like
  `Device.clean()`: a location must belong to the assigned site. Because
  `Structure.site` is nullable (unlike `Device.site`), setting a location
  with no site fills the site in from the location rather than rejecting it.
  Exposed in the form, filters, bulk edit, CSV import, table, detail panel,
  search results and the REST API. Refs #89.

- **Nearby structures as a read-only reference layer in the map edit
  widget.** The geometry widget on add/edit forms can now display the
  structures already recorded in the plugin as faded, non-interactive
  markers (same shapes and colours as the infrastructure map), so paths
  can be lined up against the surrounding plant without flipping to the
  GIS map. A new toolbar button toggles the layer (default on, persisted
  in localStorage); the viewport is fetched from the GeoJSON structures
  endpoint on pan/zoom from zoom 13, with name labels from zoom 17.
  Reference markers never intercept clicks and nothing snaps to them --
  endpoint snapping still applies only to the configured start/end
  structures. The locked start/end endpoint markers now carry the same
  name labels. Refs #83.
- **Zoom-out floor on the edit widget** -- the geometry widget no longer
  zooms out to world level (editing a single geometry never needs it);
  the floor defaults to zoom 14 (about 5 km across a typical widget) and
  is configurable via
  `PLUGINS_CONFIG['netbox_pathways']['map_widget_min_zoom']`. The
  full-page infrastructure map is unaffected.
- **Rounded `geo_length` display** -- computed pathway lengths are now rounded
  to 2 decimals (centimetres) by default instead of showing 12 decimal
  digits; even survey-grade GPS tops out around centimetre accuracy, so the
  extra digits were noise. A new
  `PLUGINS_CONFIG['netbox_pathways']['geo_length_decimals']` setting (default
  `2`, `0` = whole metres) controls how many decimal digits appear in tables,
  detail panels, and the REST/GeoJSON APIs. Sorting and
  `geo_length__gte`/`__lte` filtering are unaffected -- they always use the
  full-precision PostGIS value. Fixes #80.
- **`LICENSE` file (AGPL-3.0-or-later).** The project is now explicitly licensed under the GNU Affero General Public License v3.0 or later. The README previously referenced Apache 2.0 but no license file was ever shipped; `pyproject.toml` now declares the SPDX expression `AGPL-3.0-or-later` so PyPI metadata matches.
- **Status on the interactive map** -- the sidebar details pane now shows the clicked feature's lifecycle status as a colored badge, and a new **Hide inactive** toggle (with a gear panel choosing which statuses count as inactive, default `retired` + `abandoned`; persisted in localStorage) removes those features from every map layer. Filtering happens server-side: the GeoJSON layer endpoints and the `/info` count endpoint accept `exclude_status` (comma-separated or repeated), so viewport counts and clustering thresholds stay consistent with what is drawn. `/info` also returns the available `statuses` (value, label, color) for building filter UIs. Circuit routes are unaffected (circuits carry NetBox core statuses). Refs #68.
- **Skip-info band + optimistic `/info` revalidation on the map.** Panning and zooming no longer block on a fresh `/info` round-trip before the GeoJSON layers start loading. The frontend now uses a three-band strategy: below `MIN_DATA_ZOOM` (11) nothing renders; in the gated band, if a recent `/info` is cached the cached decision drives the immediate render and `/info` revalidates in the background with `If-None-Match` (a 304 leaves the screen untouched, a 200 reconciles only if the decision actually changed); at or above `SKIP_INFO_ZOOM` (default 17) `/info` is skipped entirely because the viewport is too small to plausibly cross any hide/cluster threshold. Configurable via `PLUGINS_CONFIG['netbox_pathways']['map_skip_info_zoom']` if a deployment hits the edge case. The pure decision logic lives in `netbox_pathways/static/netbox_pathways/src/load-strategy.ts` (`chooseLoadStrategy`, `decideSkipInfo`, `decisionsDiffer`) and is covered by vitest. `fetchMapInfo`'s callback now also signals whether the response was a 200 (fresh) or 304 (unchanged), so callers can skip the reconciliation render in the common case.
- **`status` field on the Pathway base model** -- every pathway type (`Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, `ConduitBank`) now carries a lifecycle status with the same states as structures (`planned`, `active`, `construction`, `decommissioning`, `retired`, `abandoned`; default `active`, new `PathwayStatusChoices` ChoiceSet). Surfaced everywhere structures already surface theirs: edit/bulk-edit/import forms (blank CSV column defaults to `active`), list-view filters and default table columns, detail panels, REST serializers, GraphQL filters, and global-search result attributes. The route planner's existing "Include inactive/retired" toggle now also applies to the pathway's own status: `retired` / `decommissioning` pathways are excluded from route searches by default, in addition to the existing exclusion of pathways touching retired/decommissioning structures. Structure CSV import's `status` column is now optional too (blank defaults to `active`); previously it was required. Migration `0020_pathway_status`. Refs #60.
- `opgw` (OPGW -- optical ground wire) added to `AerialTypeChoices`, selectable as the Aerial Type on Aerial Spans in forms, filters, and CSV import. Refs #59.
- **CSV bulk import for every catalogued model** -- `DirectBuried`, `Innerduct`, `ConduitJunction`, `PlannedRoute`, `SiteGeometry`, and `CircuitGeometry` gain import forms, views, and `/import/` pages; previously only `Structure`, `Conduit`, `AerialSpan`, `ConduitBank`, and `CableSegment` were importable. Every importable model's left-menu entry and list view now shows an Import button. The pathway import forms (`Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, `ConduitBank`, `PlannedRoute`) also accept `start_location` / `end_location` columns (by location name) so indoor endpoints can be imported, and `AerialSpanImportForm` no longer hard-requires structure endpoints. Import forms now cover every editable model field: `ConduitImportForm` gains `conduit_bank` and `start_junction` / `end_junction` (matched by label), `bank_position`, `start_face` / `end_face`, and owner `tenant` columns; the other pathway import forms gain `tenant`; `CableSegmentImportForm` gains an optional `sequence` (blank auto-assigns as before). Pathway rows whose endpoints are both structures no longer require a `path` value -- the straight-line path is auto-generated at import exactly as the interactive form does. A coverage test now pins every import form to its model's editable fields so new fields cannot silently go missing from CSV import. Refs #58.
- **Computed `geo_length` on Pathway and subclasses** -- the drawn length of a pathway's LineString, in metres, is now exposed as a read-only `geo_length` property computed by PostGIS (`ST_Length`) rather than entered manually. The existing `length` field stays for as-built / field-measured lengths (slack, sag, riser drops) and is now labelled "Length (m, as-built)" in detail panels alongside the new "Geo length (m, drawn)". A custom `PathwayQuerySet.with_geo_length()` adds an `_geo_length` annotation that the list views (`Pathway`, `Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, `ConduitBank`) already apply so the new sortable "Geo length (m)" table column hits PostGIS, not Python. REST and GeoJSON serializers emit `geo_length`; `PathwayFilterSet` (and the per-subclass filtersets) gain `geo_length__gte` / `geo_length__lte` URL range filters via a `GeoLengthFilterMixin`. Requires a projected, metre-based SRID (`PLUGINS_CONFIG['netbox_pathways']['srid']`) -- which is already required for the rest of the plugin's geometry support.
- **`/info` map endpoint and count-based layer gating** -- new `GET /api/plugins/pathways/geo/info/?bbox=...` returns per-layer feature counts (`structures`, `conduit_banks`, `conduits`, `aerial_spans`, `direct_buried`, `circuits`, and an `external` map for reference-mode registered layers) plus the per-layer thresholds the frontend uses to decide whether to render, client-cluster, or hide each layer. Thresholds default to `{structures: {cluster: 200, hide: 5000}, ...others: {hide: 500}}` and are overridable per-layer via `PLUGINS_CONFIG['netbox_pathways']['map_thresholds']`. The map frontend now consults `/info` on every pan/zoom and applies a single "structures clustered -> no supports" rule: whenever structures cross either threshold (client or server cluster), every pathway and reference-mode external layer is suppressed for that viewport. The hardcoded `MIN_BANK_ZOOM = 18` heuristic is removed; banks become visible whenever their viewport count is below the configured threshold. Over-budget layer toggles in the sidebar dim and display a count chip. `MapLayerRegistration` gains an optional `max_features` (default 500) for reference-mode external layers.
- **Geometry on CSV bulk import** -- `StructureImportForm` (Point) and the LineString import forms (`ConduitImportForm`, `AerialSpanImportForm`, `ConduitBankImportForm`) now expose a `location` / `path` column. Values pass through the same forgiving parser as the interactive map widget, so spreadsheets can carry GeoJSON, WKT, DMS (hemispheres optional), or Google-Maps-style decimal `lat,lon` pairs. The parser produces WGS84 and Django GIS reprojects to the configured storage SRID at save time. New helper `netbox_pathways.coord_parser.parse_geometry_input` plus `ForgivingGeometryField` are also importable by downstream code that wants the same lenient parsing.
- **Manual coordinate entry on the map widget** -- the geometry widget now has a tabbed UI with a **Map** tab (existing Leaflet/geoman editor) and a **Coordinates** tab containing a free-text editor. The textarea accepts GeoJSON (Geometry, Feature, or FeatureCollection -- first feature wins), WKT (`POINT`/`LINESTRING`/`POLYGON`), DMS (hemisphere letters optional; lat-first when omitted), and decimal `lat,lon` pairs in Google-Maps order. Invalid input is reported inline without clobbering the previous geometry. The Map tab also exposes two helper buttons: **Use my location** (`navigator.geolocation`, requires HTTPS) and **Paste lat/lon...** (an inline mini-form). On Point widgets the helpers set or replace the marker; on LineString widgets they append a vertex (the first invocation stashes a pending vertex shown as a faded marker, and the second materializes a two-vertex line). Refs #32.
- `ConduitBank.height` and `ConduitBank.width` (PositiveIntegerField, nullable). Captures duct-bank dimensions distinct from `total_conduits`. Surfaced in list tables (toggleable, off by default), forms (single and bulk), detail panel, import form, and REST API serializer. Migration `0017_conduitbank_height_width`.
- The Route tab states where each cable end sits in the plant, most precise
  place first, and says so explicitly when an end cannot be placed there --
  including when only one of the two ends can be.
- Pathways can be filtered by connected graph node through the REST API:
  `?connected_to=structure:12&connected_to=location:5`. A companion
  `?connected_to_cable_end=41:A` resolves one end of a cable to those nodes
  server-side, so the Route tab's picker sends a single query parameter no
  matter how many structures the site holds.
- Route validation reports whether a route's ends reach the cable's ends,
  alongside the existing gap check.

- **Location geometry resolves through structure identity.** `Structure.location`
  is now a one-to-one identity link ("the dcim.Location this structure IS"),
  and the map layer registry resolves `dcim.Location` FK targets through it
  (`pathways_structure__geometry`). Reference-mode layers may declare
  `geometry_field` as an ordered tuple (e.g. `("location", "site")`) that
  falls back with SQL COALESCE, shared by the GeoJSON endpoint and the `/info`
  counts. Pathway location endpoints whose Location has an identity structure
  are snapped and validated like structure endpoints, and the map edit
  widget's nearby-structures layer anchors polygon-footprint structures at
  their centroid instead of skipping them. Refs #90.

### Changed

- The Conduits table on a conduit bank's detail page now shows the Bank
  Position column instead of the redundant Conduit Bank column, which only
  linked back to the page being viewed. The standalone Conduits list view
  is unchanged. Requested by @marcusyuri. Refs #76.

- **Innerduct color is now picked from NetBox's color palette** instead of
  typed as free text. The edit, bulk-edit and list-filter forms use the core
  color widget, and innerduct tables -- including the one on a conduit's
  detail page -- render the value as a swatch rather than a color name.
  Refs #79.

  Migration `0022_innerduct_color_hex` converts the existing free-text
  values: names in the palette become their hex code, and `slate`,
  `violet`, `magenta`, `silver`, `natural`, `clear` and US "gray" spellings
  map onto the nearest palette entry. **A value matching none of these is
  cleared**, because the column narrows from 50 characters to 6; the
  migration prints every value it drops, so check that list before
  migrating a database with hand-written colors. Reversing the migration
  restores palette names.

  CSV import still accepts a color name (`Blue`) or a hex code (`2196f3`)
  and rejects anything it cannot resolve, so existing import files keep
  working. Color is no longer indexed for global search: it holds a hex
  code now, which nobody searches for.

- **The innerduct list filter now renders its size and position fields.**
  `InnerductFilterSet` accepted both parameters already, but the filter
  form omitted them, so they could only be reached by editing the URL.

- **The base-layer selector now sits bottom-right on every map.** The
  full-page map already put it there; the geometry edit widget and the
  detail-page mini maps had it top-right. Refs #75.

- **The kiosk-mode button moved to the top-right of the full-page map**,
  matching the edit widget's full-screen button and the detail panel's
  expand button, so the same action is in the same corner throughout.
  Note that the kiosk sidebar overlays that corner when it is open; close
  it with Escape or its own close button to reach the exit-kiosk button.
  Refs #75.

- **BREAKING: `Structure.location` is now a FK to `dcim.Location`; the
  geometry moved to `Structure.geometry`.** `location` previously held the
  Point/Polygon geometry, which made it the odd one out -- `location` means
  `dcim.Location` everywhere else in this plugin (`Pathway.start_location`,
  `PathwayLocation.location`) and in core NetBox (`Device.location`).
  The geometry column is renamed to `geometry`, matching
  `SiteGeometry.geometry` and `CircuitGeometry.geometry`.

  The `location` key survives in the REST API, GraphQL, CSV import/export
  and the form, but its **meaning changes** from a geometry to a nested
  Location object. Existing API consumers, scripts, saved table
  configurations and CSV templates that read or write `structure.location`
  expecting coordinates must be updated to `geometry`. Migration
  `0021_structure_geometry_and_location` renames the column in place, so no
  data is lost. Refs #89.

- **BREAKING: `splice_closure` removed from `StructureTypeChoices`.** A
  splice closure is `dcim.Device`-shaped -- it has FrontPorts, RearPorts and
  Modules -- and lives *in* a structure rather than *being* one. A Structure
  typed `splice_closure` could only ever be a map pin, and it invited
  modelling the same physical closure twice (once as a Structure, once as a
  Device) with two site anchors that could disagree. Existing rows have
  `structure_type` blanked by the migration; reclassify them to the real
  container type (handhole, pedestal, cabinet, ...). Refs #89.

- **`Pathway.path` is now optional for indoor pathways.** A pathway whose both
  endpoints are locations (rooms, floors) can be saved without a geographic
  path -- NetBox locations carry no coordinates, so previously such pathways
  could not be created at all without drawing a meaningless map line. A path
  is still required whenever either endpoint is geographic (a structure or,
  for conduits, a junction); this rule now lives in `Pathway.clean()` instead
  of the database NOT NULL constraint. Pathless indoor pathways are excluded
  from the GeoJSON map layers. Innerducts now inherit locations (not just
  structures) from their parent conduit, at validation time as well as save
  time. Migration `0019_alter_pathway_path`.
- **`AerialSpan.attachment_height` is now per-endpoint.** The single
  `attachment_height` field is replaced by `start_attachment_height` and
  `end_attachment_height` (both nullable floats, meters). A read-only
  `attachment_height` property returns the mean of the two sides (or whichever
  side is populated; `None` if both are unset). Existing data is preserved on
  migration: the previous single value is copied into both per-side fields.
  Migration `0018_aerialspan_attachment_height_per_side`.

- **BREAKING: CSV import column `attachment_height` is removed.** Update imports to use
  `start_attachment_height` and `end_attachment_height`. The REST API field
  `attachment_height` becomes read-only and derived; clients writing to it
  must target the per-side fields.
- The route planner prefills a cable endpoint only when it resolves to exactly
  one structure.
- **`netbox_pathways.filters` is now `netbox_pathways.filtersets`.** NetBox
  resolves plugin filtersets at `<app>.filtersets`, which the old module name
  broke. Code importing `from netbox_pathways.filters import ...` must update
  the path; the filterset classes themselves are unchanged.

### Removed

- The undocumented `/plugins/pathways/adjacency/` endpoint, superseded by the
  `connected_to` filter on the pathways REST API.

- **`Pathway.start_location` / `end_location` now use `PROTECT`.** Deleting a
  `dcim.Location` referenced as a pathway endpoint is blocked instead of
  silently nulling the endpoint. Refs #90.

- **Migration note:** upgrading fails loudly if two structures share one
  `location`; reassign or clear the duplicates first. Refs #90.

### Fixed

- **Server-side structure clusters ignored filter parameters.** The
  clustered response at low zoom rebuilt its queryset from scratch, so any
  filterset parameter on the request (`occupied`, `structure_type`, `q`,
  ...) applied to the plain features but not to the cluster counts.
  Clusters now aggregate the same filtered queryset the plain branch
  serializes. Refs #112.

- **The nearby-structures layer drew the structure you were editing.** A
  Structure edit form fetches the surrounding structures for context, and the
  record being edited came back with them -- so a faded read-only copy sat
  directly under the editable marker, and once the marker was dragged the copy
  stayed behind at the old position looking like a second structure. The
  widget now tells the layer which record to skip, matched by ID rather than
  by position, so it stays hidden wherever the marker goes. Structures that
  genuinely share the location are still drawn. Refs #75.

- **The "Show nearby structures" button looked the same on and off.** Its
  pressed state was a `#f4f4f4` tint, indistinguishable from Leaflet's white
  control background -- and the same colour Leaflet already uses for plain
  hover -- so a layer that persists across page loads gave no clue which way
  it was set. The button now fills with the accent colour while the layer is
  on, and its tooltip and screen-reader label switch between "Show" and
  "Hide". Refs #75.

- **Expanding a detail-page map shifted the whole page sideways.** Bootstrap
  hides the scrollbar when a modal opens and adds an equal `padding-right` to
  replace the width it assumes it reclaimed -- but NetBox reserves that width
  permanently (`scrollbar-gutter: stable` on `:root` above 992px), so nothing
  was reclaimed and the padding was pure surplus. Content jumped left on open
  and back on close. The map modal now releases the gutter while it is up, so
  Bootstrap's arithmetic comes out even. Refs #75.

- **The detail-page map now re-measures when its box changes.** Leaflet sizes
  its panes once, from the container width at init, and an object detail page
  is often still settling then. A ResizeObserver replaces the fixed 150ms
  guess the panel was using, and the map's sizing moved out of inline styles
  into `.pw-detail-map`. Refs #75.

- **Structures with a polygon geometry broke the whole structures layer.**
  The map assumed every structure feature was a marker and asked the layer
  Leaflet built for its `getLatLng()`; a footprint polygon has no such method,
  so rendering threw `TypeError: I.getLatLng is not a function` part-way
  through and no structures appeared at all -- silently on first load, where
  the fetch wrapper swallowed the error, and with a console error when the
  layer was toggled off and on from cache. Structure layers are now located by
  marker position or bounds center, whichever the layer supports, and the same
  assumption is gone from the sidebar highlight and focus-dimming paths, which
  would have thrown on `setIcon` / `setOpacity` next. Reported by
  @JulianJacobi. Fixes #96.

- **The Route tab on a Cable raised `TemplateDoesNotExist` on NetBox 4.6.**
  `cable_route_tab.html` extended `dcim/cable.html`, which NetBox 4.6 removed
  when the cable detail view moved to the layout system, so opening the Route
  tab of any cable returned a server error. The template now extends
  `generic/object.html`, like every other detail template in this plugin, and
  renders identically on 4.5 and 4.6. Contributed by @JulianJacobi. Fixes #73.

- **The map and route planner failed to load for users on a non-English
  locale.** Django localizes numbers when a template renders them, so under
  a language that uses a comma as the decimal separator (German, French,
  Spanish, ...) the map center was written into the page as
  `center: [52,42, 10,78]` -- a four-element array -- and Leaflet threw
  `TypeError: null is not an object (evaluating 't.lat')`, leaving a blank
  map. The client config is now built in the view and emitted with Django's
  `json_script`, which is locale-independent and escapes the payload against
  script-tag breakout. Reported and diagnosed by @JulianJacobi. Fixes #93.

- **The map panel on a Location detail page ignored the structures in that
  location.** It only drew pathways whose start or end was the location, plus
  those pathways' endpoint structures -- so a location holding structures but
  touched by no pathway rendered no panel at all. It now shows the structures
  in the location, and walks the location tree the way NetBox's own related
  object counts do, so viewing a parent location includes its children instead
  of contradicting the count shown beside it. Structures are also de-duplicated:
  two pathways sharing an endpoint previously stacked two identical markers on
  the same coordinates. Structures present only as the far end of a pathway
  leaving the location are drawn faded (a new `muted` flag on the panel's point
  data) so the location's own plant reads first. Refs #89.

- **Selecting an external-layer point feature in the map sidebar did nothing.**
  Clicking a point feature from a registered external layer (e.g. FMS slack
  loops or splice closures) in the Features pane threw a TypeError in the
  highlight step -- the code assumed every non-structure feature was a
  polyline -- which silently aborted both the zoom-to-feature and the detail
  panel rendering. Circle markers are now highlighted in place, the detail
  panel shows the feature's properties, and `LayerDetail.url_template` is
  rendered as the documented "View Details" link (previously it was wrongly
  fetched as a JSON endpoint, yielding a network error instead of details).
  The inline rename pencil is hidden for external features without a REST
  endpoint. Fixes #81.

- **Map page crashed when any structure had a polygon footprint.** The
  initial-extent query trimmed GPS outliers with `ST_X()`/`ST_Y()` on raw
  structure locations, but those functions only accept points, so a single
  polygon-footprint structure raised `InternalError: Argument to ST_Y() must
  have type POINT` and 500ed the map and route planner. Outlier trimming now
  compares each geometry's centroid (identical behavior for points) while the
  extent itself still uses the full geometry, so footprints are covered edge
  to edge. Fixes #71.
- **List-view Import buttons were dead links.** The plugin registered its
  import URLs as `<model>_import`, but NetBox's list-view `BulkImport` action
  reverses `<model>_bulk_import`, so every Import button on object tables
  rendered without an href. The URL names now follow the NetBox convention
  (the `/import/` paths themselves are unchanged). Fixes #58.
- `ConduitBankImportForm` was missing the `length` column that the GUI add
  form exposes. Fixes #58.

- Object selector modals no longer fail with a blank grey overlay. NetBox
  resolves plugin filter forms at `<app>.forms.<Model>FilterForm` and
  filtersets at `<app>.filtersets.<Model>FilterSet`; the plugin's modules were
  named `filterforms.py` and `filters.py`, so every `selector=True` field
  returned a server error when its selector button was clicked (#106).

- **The Route tab's "Add First Segment" pathway picker offered nothing.**
  The add-segment view hand-rendered a `<select>` filled from a single
  guessed structure -- `Structure.objects.first()` when the cable's A
  termination could not be pinned down more precisely -- so the dropdown was
  usually empty and typing in it showed "no results found". The picker is now
  a `DynamicModelChoiceField` filtered by the cable end's real candidate
  nodes, structures and locations alike, with a "Show all pathways" fallback
  when the end cannot be placed in the plant. Two
  behavior changes: the pathway field is now required (an empty submission
  used to silently create a segment with no pathway), and the picker's
  choice list is no longer capped by what the server chose to pre-render --
  it queries the same filtered/unfiltered set the user sees. Fixes #106.

- **Mid-route pathway suggestions could be wrong, and were empty at a branch
  tap.** Adding a segment after an existing one derived the entry point from
  the previous pathway's end endpoint regardless of which way the cable
  travels, so it could offer the pathways behind the cable rather than ahead
  of it -- and for a conduit whose far end is a ConduitJunction it resolved
  nothing and silently listed every pathway instead. The picker now offers
  both endpoints of the previous pathway, and junction endpoints resolve.

## [0.2.2] - 2026-06-30

### Fixed

- **Geometry map widget renders blank on NetBox 4.6 / Django 6.0.** Django 6.0
  stopped exposing the top-level `id`, `name`, and `geom_type` template-context
  variables from `BaseGeometryWidget` (they moved under `widget`). The map
  widget template read them at the top level, so on Django 6.0 the hidden
  geometry input rendered with an empty `name` (the form submitted no geometry
  and validation failed with "No geometry value submitted") and the map
  container rendered with an empty `data-field-id` (the Leaflet/geoman
  initializer bailed and no map appeared) -- making it impossible to add a
  Structure or draw a Pathway. `PathwaysMapWidget.get_context` now re-exposes
  these variables; the fix stays backwards compatible with NetBox 4.5 /
  Django 5.2. Fixes #52.

## [0.2.1] - 2026-05-07

### Fixed

- **`CircuitGeometry.path` SRID drift** -- `0004_circuit_geometry` no longer hardcodes `srid=3348`; it now uses `_SRID = get_srid()` like the other migrations, so the column SRID follows `PLUGINS_CONFIG['netbox_pathways']['srid']`. Installs whose configured SRID differs from `3348` were silently storing the path column at `3348` and rejecting every form submission with `Geometry SRID does not match column SRID` (issue #5, #29).

### Added

- **System check `netbox_pathways.E001`** -- compares introspected `geometry_columns` SRIDs against `get_srid()` and emits a `checks.Error` (with remediation hint) whenever a stored column SRID disagrees with the configured value. Runs on `manage.py check` and `manage.py migrate`. Catches the same drift surfaced in #5/#29 before users hit it through the UI.

## [0.2.0] - 2026-05-06

### Added

- **GraphQL API** -- new `netbox_pathways/graphql/` module exposing every plugin model (`Structure`, `SiteGeometry`, `CircuitGeometry`, `Pathway`, `ConduitBank`, `Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, `ConduitJunction`, `PathwayLocation`, `CableSegment`, `PlannedRoute`) on the NetBox `/graphql/` endpoint via Strawberry types, filter inputs, and a query class wired through `PluginConfig.graphql_schema`. Geometry fields are excluded from GraphQL types -- continue to use the GeoJSON REST endpoints under `/api/plugins/pathways/geo/` for spatial queries.
- **Aerial overlashing** -- new `CableSegment.lashed_with` symmetric self-`ManyToManyField`. Captures that this segment shares a single lash wire with one or more other cable segments on the same aerial span. Symmetrical: adding a peer auto-adds the reverse. Per-segment, since a cable can be partly overlashed (aerial segments) and partly not (underground segments along the same route). New `lashed_cables` `@property` on `CableSegment` returns the `dcim.Cable` instances of every peer segment.
- **Installer tracking** -- new `installed_by` FK to `tenancy.Tenant` on `Structure` and `Pathway` (and all subclasses), capturing the contractor or workforce that physically installed the asset, distinct from `tenant` (served customer / asset owner).
- **Commissioned date** -- new `commissioned_date` `DateField` on `Structure` and `Pathway`, alongside the existing `installation_date`. Captures handover / acceptance date which routinely differs from install date for outside-plant work.
- **Abandoned-in-place status** -- new `StructureStatusChoices.STATUS_ABANDONED` value with display label `Abandoned in place` and color `gray`. Distinct from `decommissioning` / `retired`: an abandoned-in-place asset is still physically present but no longer in service.

### Changed

- Forms, tables, filters, REST API serializers, search indexes, and detail panels updated for the three new fields/values across `Structure`, `Pathway`, `Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, and `ConduitBank`.
- `CableSegment` form, filterset, filter form, REST serializer, and detail view updated for `lashed_with` (multi-select). The detail view shows a "Lashed With" table panel listing every peer segment (filtered via `lashed_with_id`); the panel hides itself when the segment has no peers via a new `HideIfEmptyObjectsTablePanel` subclass in `ui/panels.py`. The list-view table omits a column for the relationship.

## [0.1.0] - 2026-04-28

Initial public release. Documents physical cable plant infrastructure with PostGIS integration: structures, pathways, conduits, banks, junctions, cable routing, pull sheets, and a GeoJSON API for QGIS / GIS clients.

### Added

- **Structures** -- poles, manholes, cabinets, equipment rooms, etc., with PostGIS point or polygon geometry.
- **Pathways** -- conduits, aerial spans, direct buried, innerducts, cable trays, raceways, with PostGIS line geometry.
- **Conduit banks and junctions** -- model conduit bank configurations and mid-span Y-tees.
- **Cable routing** -- track which `dcim.Cable` instances traverse which pathways, in sequence.
- **Pull sheets** -- printable cable routing documents for field crews.
- **Indoor / Outdoor** -- pathways can terminate at structures (outdoor) or NetBox `dcim.Location` (indoor).
- **GeoJSON API** under `/api/plugins/pathways/geo/` for QGIS / OGR consumption.
- **QGIS integration** -- bundled `.qml` style files and a `manage.py generate_qgis_project` command that emits a pre-configured `.qgs` project.
- **Geometry editing** -- draw and edit geometries directly in NetBox forms via Leaflet map widgets.
- **Interactive map** built into the plugin for quick visualization.
- **REST API** for all models + GeoJSON variants under `/api/plugins/pathways/geo/`.

### Toolkit

- Canonical 5 GHA workflows (ci, publish, docs, release-drafter, pr-title) with PyPI Trusted Publishing and OIDC Codecov.
- `docs/zensical.toml` documentation site auto-deployed to GitHub Pages.
- `.pre-commit-config.yaml` with ruff hooks + standard pre-commit-hooks + a `commit-msg` stage that rejects AI / Claude attribution lines.
- `.git-template/hooks/commit-msg` (canonical hook tracked in-tree).
- `uv.lock` committed for reproducible CI / dev environments.
- LICENSE: Apache 2.0.

### Notes

- The `srid` setting in `PLUGINS_CONFIG` is **immutable after data has been loaded** (see README warning). Choose carefully before first deployment.
- SlackLoop model was removed in favor of the slack-loop tracking that lives in `netbox-fms` (its closure-cable-entry workflow is the right home for it). The `slack_loop_location` PointField on `Structure` is unaffected.
