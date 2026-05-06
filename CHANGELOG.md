# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
