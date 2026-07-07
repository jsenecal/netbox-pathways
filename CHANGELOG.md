# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `opgw` (OPGW -- optical ground wire) added to `AerialTypeChoices`, selectable as the Aerial Type on Aerial Spans in forms, filters, and CSV import. Refs #59.
- **CSV bulk import for every catalogued model** -- `DirectBuried`, `Innerduct`, `ConduitJunction`, `PlannedRoute`, `SiteGeometry`, and `CircuitGeometry` gain import forms, views, and `/import/` pages; previously only `Structure`, `Conduit`, `AerialSpan`, `ConduitBank`, and `CableSegment` were importable. Every importable model's left-menu entry and list view now shows an Import button. The pathway import forms (`Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, `ConduitBank`, `PlannedRoute`) also accept `start_location` / `end_location` columns (by location name) so indoor endpoints can be imported, and `AerialSpanImportForm` no longer hard-requires structure endpoints. Import forms now cover every editable model field: `ConduitImportForm` gains `conduit_bank` and `start_junction` / `end_junction` (matched by label), `bank_position`, `start_face` / `end_face`, and owner `tenant` columns; the other pathway import forms gain `tenant`; `CableSegmentImportForm` gains an optional `sequence` (blank auto-assigns as before). Pathway rows whose endpoints are both structures no longer require a `path` value -- the straight-line path is auto-generated at import exactly as the interactive form does. A coverage test now pins every import form to its model's editable fields so new fields cannot silently go missing from CSV import. Refs #58.
- **Computed `geo_length` on Pathway and subclasses** -- the drawn length of a pathway's LineString, in metres, is now exposed as a read-only `geo_length` property computed by PostGIS (`ST_Length`) rather than entered manually. The existing `length` field stays for as-built / field-measured lengths (slack, sag, riser drops) and is now labelled "Length (m, as-built)" in detail panels alongside the new "Geo length (m, drawn)". A custom `PathwayQuerySet.with_geo_length()` adds an `_geo_length` annotation that the list views (`Pathway`, `Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`, `ConduitBank`) already apply so the new sortable "Geo length (m)" table column hits PostGIS, not Python. REST and GeoJSON serializers emit `geo_length`; `PathwayFilterSet` (and the per-subclass filtersets) gain `geo_length__gte` / `geo_length__lte` URL range filters via a `GeoLengthFilterMixin`. Requires a projected, metre-based SRID (`PLUGINS_CONFIG['netbox_pathways']['srid']`) -- which is already required for the rest of the plugin's geometry support.
- **`/info` map endpoint and count-based layer gating** -- new `GET /api/plugins/pathways/geo/info/?bbox=...` returns per-layer feature counts (`structures`, `conduit_banks`, `conduits`, `aerial_spans`, `direct_buried`, `circuits`, and an `external` map for reference-mode registered layers) plus the per-layer thresholds the frontend uses to decide whether to render, client-cluster, or hide each layer. Thresholds default to `{structures: {cluster: 200, hide: 5000}, ...others: {hide: 500}}` and are overridable per-layer via `PLUGINS_CONFIG['netbox_pathways']['map_thresholds']`. The map frontend now consults `/info` on every pan/zoom and applies a single "structures clustered -> no supports" rule: whenever structures cross either threshold (client or server cluster), every pathway and reference-mode external layer is suppressed for that viewport. The hardcoded `MIN_BANK_ZOOM = 18` heuristic is removed; banks become visible whenever their viewport count is below the configured threshold. Over-budget layer toggles in the sidebar dim and display a count chip. `MapLayerRegistration` gains an optional `max_features` (default 500) for reference-mode external layers.
- **Geometry on CSV bulk import** -- `StructureImportForm` (Point) and the LineString import forms (`ConduitImportForm`, `AerialSpanImportForm`, `ConduitBankImportForm`) now expose a `location` / `path` column. Values pass through the same forgiving parser as the interactive map widget, so spreadsheets can carry GeoJSON, WKT, DMS (hemispheres optional), or Google-Maps-style decimal `lat,lon` pairs. The parser produces WGS84 and Django GIS reprojects to the configured storage SRID at save time. New helper `netbox_pathways.coord_parser.parse_geometry_input` plus `ForgivingGeometryField` are also importable by downstream code that wants the same lenient parsing.
- **Manual coordinate entry on the map widget** -- the geometry widget now has a tabbed UI with a **Map** tab (existing Leaflet/geoman editor) and a **Coordinates** tab containing a free-text editor. The textarea accepts GeoJSON (Geometry, Feature, or FeatureCollection -- first feature wins), WKT (`POINT`/`LINESTRING`/`POLYGON`), DMS (hemisphere letters optional; lat-first when omitted), and decimal `lat,lon` pairs in Google-Maps order. Invalid input is reported inline without clobbering the previous geometry. The Map tab also exposes two helper buttons: **Use my location** (`navigator.geolocation`, requires HTTPS) and **Paste lat/lon...** (an inline mini-form). On Point widgets the helpers set or replace the marker; on LineString widgets they append a vertex (the first invocation stashes a pending vertex shown as a faded marker, and the second materializes a two-vertex line). Refs #32.
- `ConduitBank.height` and `ConduitBank.width` (PositiveIntegerField, nullable). Captures duct-bank dimensions distinct from `total_conduits`. Surfaced in list tables (toggleable, off by default), forms (single and bulk), detail panel, import form, and REST API serializer. Migration `0017_conduitbank_height_width`.

### Changed

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

### Breaking

- **CSV import column `attachment_height` is removed.** Update imports to use
  `start_attachment_height` and `end_attachment_height`. The REST API field
  `attachment_height` becomes read-only and derived; clients writing to it
  must target the per-side fields.

### Fixed

- **List-view Import buttons were dead links.** The plugin registered its
  import URLs as `<model>_import`, but NetBox's list-view `BulkImport` action
  reverses `<model>_bulk_import`, so every Import button on object tables
  rendered without an href. The URL names now follow the NetBox convention
  (the `/import/` paths themselves are unchanged). Fixes #58.
- `ConduitBankImportForm` was missing the `length` column that the GUI add
  form exposes. Fixes #58.

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
