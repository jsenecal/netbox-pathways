# netbox-pathways

> **Under active development -- alpha.** netbox-pathways is pre-1.0 and changing fast. Models, migrations, REST/GeoJSON endpoints, and configuration keys may break between releases without deprecation cycles. Pin an exact version in production, expect to read the [CHANGELOG](CHANGELOG.md) before every upgrade, and back up your database before running migrations. Issue reports and PRs are very welcome.

> A NetBox plugin for documenting physical cable plant infrastructure with PostGIS integration. Track conduits, aerial spans, structures, and cable routing with geographic data, comparable to SmallWorld or ArcGIS with ArcFM for outside/inside plant documentation.

[![PyPI](https://img.shields.io/pypi/v/netbox-pathways.svg)](https://pypi.org/project/netbox-pathways/)
[![Python](https://img.shields.io/pypi/pyversions/netbox-pathways.svg)](https://pypi.org/project/netbox-pathways/)
[![NetBox](https://img.shields.io/badge/NetBox-4.5%2B-success.svg)](https://github.com/netbox-community/netbox)
[![CI](https://github.com/jsenecal/netbox-pathways/actions/workflows/ci.yml/badge.svg)](https://github.com/jsenecal/netbox-pathways/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jsenecal/netbox-pathways/branch/main/graph/badge.svg)](https://codecov.io/gh/jsenecal/netbox-pathways)
[![Documentation](https://img.shields.io/badge/docs-jsenecal.github.io-blue)](https://jsenecal.github.io/netbox-pathways/)
![Status](https://img.shields.io/badge/status-alpha-orange)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

> Local coverage note: `pytest --cov` run inside the devcontainer
> against `/opt/netbox/venv` may report 0% due to an editable-install
> / Django app-load timing quirk. For accurate local coverage use
> `uv venv && source .venv/bin/activate && uv pip install -e ".[dev]" && pytest --cov=netbox_pathways`,
> or rely on the Codecov upload from CI.

## Features

- **Structures** -- poles, manholes, cabinets, equipment rooms, and more with PostGIS geometry (point or polygon).
- **Pathways** -- conduits, aerial spans, direct buried, innerducts, cable trays with PostGIS line geometry; a computed `geo_length` (PostGIS `ST_Length`) sits alongside the manual as-built `length` so the drawn-versus-field distinction is always visible and sortable.
- **Conduit Banks and Junctions** -- model conduit bank configurations and mid-span Y-tees.
- **Cable Routing** -- track which NetBox cables traverse which pathways, in sequence.
- **Pull Sheets** -- printable cable routing documents for field crews.
- **GeoJSON API** -- standard GeoJSON endpoints for QGIS and other GIS clients.
- **QGIS Integration** -- style files, project generator, and documentation.
- **Geometry Editing** -- draw and edit geometries directly in NetBox forms via Leaflet map widgets, or paste GeoJSON / WKT / DMS / decimal `lat,lon` in the Coordinates tab. "Use my location" (mobile GPS) and "Paste lat/lon..." helpers place a marker on Point widgets or append a vertex on LineString widgets.
- **Interactive Map** -- built-in Leaflet map for quick visualization.
- **Indoor / Outdoor** -- pathways can terminate at structures (outdoor) or NetBox locations (indoor).

## Compatibility

| Plugin version  | NetBox version       | Python    | PostgreSQL           |
|-----------------|----------------------|-----------|----------------------|
| 0.1.x -- 0.2.1  | 4.5.3 -- 4.5.x       | 3.12-3.14 | 16+ with PostGIS 3.4+|
| 0.2.2+          | 4.5.3+ (incl. 4.6.x) | 3.12-3.14 | 16+ with PostGIS 3.4+|

> NetBox 4.6 ships Django 6.0. Plugin versions 0.2.1 and earlier do not render
> the geometry map widget on NetBox 4.6 (issue #52); upgrade to 0.2.2 or later
> for NetBox 4.6 support.

## Installation

> NetBox runs on plain PostgreSQL by default. This plugin requires PostGIS, so installing it on an existing NetBox deployment means changing your database setup. The short version is below; see [PostGIS Setup](https://jsenecal.github.io/netbox-pathways/getting-started/postgis-setup/) in the docs for the full walkthrough (system libraries, container images, migrating an existing database).

### 1. PostGIS prerequisites

Install the GIS system libraries on every NetBox host (web workers and `rq`), and PostGIS on the database server:

```bash
# Debian / Ubuntu (NetBox host)
sudo apt-get install -y gdal-bin libgdal-dev libgeos-dev libproj-dev binutils

# Database server: PostgreSQL 16+ with the PostGIS 3.4 package, then:
psql -d netbox -c "CREATE EXTENSION IF NOT EXISTS postgis;"
```

### 2. Switch NetBox to the PostGIS database backend

In `configuration.py`, the default `DATABASES` engine is plain PostgreSQL. Change `ENGINE` to the PostGIS backend (the standard `django.db.backends.postgresql` engine appears to work but fails the first time a geometry column is created):

```python
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",  # was django.db.backends.postgresql
        "NAME": "netbox",
        "USER": "netbox",
        "PASSWORD": "...",
        "HOST": "localhost",
        "PORT": "",
        "CONN_MAX_AGE": 300,
    },
}
```

### 3. Install the plugin and configure it

```bash
pip install netbox-pathways
```

```python
PLUGINS = ["netbox_pathways"]

PLUGINS_CONFIG = {
    "netbox_pathways": {
        "srid": 3348,           # REQUIRED -- your EPSG code (see SRID warning below)
        "map_center_lat": 45.5, # default map center latitude (optional)
        "map_center_lon": -73.5,# default map center longitude (optional)
        "map_zoom": 10,         # default map zoom level (optional)
    },
}
```

### 4. Migrate, collect static, restart

```bash
cd /opt/netbox/netbox
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

If `migrate` fails with errors mentioning `postgis`, `gdal`, or `geos`, the database backend is still on plain PostgreSQL or the GIS system libraries are missing on the NetBox host. The [PostGIS Setup](https://jsenecal.github.io/netbox-pathways/getting-started/postgis-setup/) page covers diagnosis and recovery.

## Configuration

### SRID is immutable after installation

The `srid` setting defines the coordinate reference system used for **all** geometry columns in the database. It is baked into the database schema at migration time.

**Changing the SRID after data has been loaded WILL CORRUPT YOUR SPATIAL DATA.** PostgreSQL / PostGIS does NOT automatically re-project existing coordinates when the column SRID changes. Geometries will have wrong coordinates in the new CRS with no way to recover them automatically.

Choose your SRID carefully before first deployment. Common choices:

| EPSG    | Name                                          | Notes                                            |
|---------|-----------------------------------------------|--------------------------------------------------|
| `4326`  | WGS84 (GPS coordinates, degrees)              | Global, but distorts distances and areas.        |
| `3857`  | Web Mercator (meters)                         | Used by Google Maps, OSM tiles.                  |
| `3348`  | NAD83(CSRS) / Statistics Canada Lambert (m)   | Good for Canada.                                 |
| `2154`  | RGF93 / Lambert-93 (meters)                   | Good for France.                                 |
| `32632` | WGS84 / UTM zone 32N (meters)                 | Good for central Europe.                         |

If you need to change SRID after deployment, you must manually re-project all geometry data using PostGIS `ST_Transform()` and update the column SRID definitions. This is an advanced DBA operation; back up everything first.

## QGIS quick start

Generate a QGIS project with all layers pre-configured:

```bash
python manage.py generate_qgis_project \
    --url https://your-netbox \
    --token your-api-token
```

Open the generated `.qgs` file in QGIS. Style files (`.qml`) ship under `static/netbox_pathways/qgis/` and can be loaded via Layer Properties > Style > Load Style.

## REST and GeoJSON API

All resources are exposed under `/api/plugins/pathways/`. GeoJSON variants live under `/api/plugins/pathways/geo/` for direct QGIS / OGR consumption. See [API Examples](https://jsenecal.github.io/netbox-pathways/developer/api-examples/) for full endpoint coverage.

## GraphQL

Every Pathways model is exposed on NetBox's `/graphql/` endpoint (single and `_list` queries: `structure`, `structure_list`, `pathway`, `pathway_list`, `conduit`, `conduit_list`, etc.). Geometry fields are intentionally omitted -- query the GeoJSON REST endpoints for spatial data.

## Documentation

Full documentation: **[jsenecal.github.io/netbox-pathways](https://jsenecal.github.io/netbox-pathways/)**

- [Installation](https://jsenecal.github.io/netbox-pathways/getting-started/installation/)
- [PostGIS Setup](https://jsenecal.github.io/netbox-pathways/getting-started/postgis-setup/)
- [SRID Selection](https://jsenecal.github.io/netbox-pathways/getting-started/srid/)
- [Configuration](https://jsenecal.github.io/netbox-pathways/getting-started/configuration/)
- [Concepts](https://jsenecal.github.io/netbox-pathways/user-guide/concepts/)
- [QGIS Integration](https://jsenecal.github.io/netbox-pathways/user-guide/qgis-integration/)
- [Architecture](https://jsenecal.github.io/netbox-pathways/developer/architecture/)
- [GeoJSON API reference](https://jsenecal.github.io/netbox-pathways/reference/geojson-api/)

## Related plugins

netbox-pathways is part of a three-plugin set that models the full optical transport stack:

- **[netbox-fms](https://github.com/jsenecal/netbox-fms)** -- Fiber Management System. Defines fiber cable construction (buffer tubes, ribbons, strands), plans splices in closures, and provisions end-to-end fiber circuits. Pathways tracks *where cables run*; FMS tracks *what is inside them and how strands are spliced*.
- **[netbox-wdm](https://github.com/jsenecal/netbox-wdm)** -- WDM (Wavelength Division Multiplexing) device management. Models ITU channel plans, ROADM mappings, and wavelength services that ride on top of the fiber circuits FMS provisions, over the cables routed through Pathways.

## Contributing

PRs welcome. Use conventional-commits PR titles (`feat:`, `fix:`, `chore:`, `docs:`, ...) -- release-drafter assembles release notes from them. Run `make setup` after cloning to install dev dependencies and the pre-commit hooks (including the AI-attribution-rejecting `commit-msg` hook).

## License

[Apache License 2.0](LICENSE).
