# netbox-pathways

> A NetBox plugin for documenting physical cable plant infrastructure with PostGIS integration. Track conduits, aerial spans, structures, and cable routing with geographic data, comparable to SmallWorld or ArcGIS with ArcFM for outside/inside plant documentation.

[![PyPI](https://img.shields.io/pypi/v/netbox-pathways.svg)](https://pypi.org/project/netbox-pathways/)
[![Python](https://img.shields.io/pypi/pyversions/netbox-pathways.svg)](https://pypi.org/project/netbox-pathways/)
[![NetBox](https://img.shields.io/badge/NetBox-4.5%2B-success.svg)](https://github.com/netbox-community/netbox)
[![CI](https://github.com/jsenecal/netbox-pathways/actions/workflows/ci.yml/badge.svg)](https://github.com/jsenecal/netbox-pathways/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/jsenecal/netbox-pathways/branch/main/graph/badge.svg)](https://codecov.io/gh/jsenecal/netbox-pathways)
[![Documentation](https://img.shields.io/badge/docs-jsenecal.github.io-blue)](https://jsenecal.github.io/netbox-pathways/)
![Status](https://img.shields.io/badge/status-alpha-orange)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Features

- **Structures** -- poles, manholes, cabinets, equipment rooms, and more with PostGIS geometry (point or polygon).
- **Pathways** -- conduits, aerial spans, direct buried, innerducts, cable trays with PostGIS line geometry.
- **Conduit Banks and Junctions** -- model conduit bank configurations and mid-span Y-tees.
- **Cable Routing** -- track which NetBox cables traverse which pathways, in sequence.
- **Pull Sheets** -- printable cable routing documents for field crews.
- **GeoJSON API** -- standard GeoJSON endpoints for QGIS and other GIS clients.
- **QGIS Integration** -- style files, project generator, and documentation.
- **Geometry Editing** -- draw and edit geometries directly in NetBox forms via Leaflet map widgets.
- **Interactive Map** -- built-in Leaflet map for quick visualization.
- **Indoor / Outdoor** -- pathways can terminate at structures (outdoor) or NetBox locations (indoor).

## Compatibility

| Plugin version | NetBox version | Python    | PostgreSQL          |
|----------------|----------------|-----------|---------------------|
| 0.1.x          | 4.5.3+         | 3.12-3.14 | 16+ with PostGIS 3.4|

## Installation

```bash
pip install netbox-pathways
```

In your NetBox `configuration.py`:

```python
PLUGINS = ["netbox_pathways"]

PLUGINS_CONFIG = {
    "netbox_pathways": {
        "srid": 3348,           # REQUIRED -- your EPSG code (see warning below)
        "map_center_lat": 45.5, # default map center latitude (optional)
        "map_center_lon": -73.5,# default map center longitude (optional)
        "map_zoom": 10,         # default map zoom level (optional)
    },
}
```

Run migrations and restart:

```bash
cd /opt/netbox/netbox
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

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

## Documentation

Full documentation: **[jsenecal.github.io/netbox-pathways](https://jsenecal.github.io/netbox-pathways/)**

- [Installation](https://jsenecal.github.io/netbox-pathways/getting-started/installation/)
- [Configuration](https://jsenecal.github.io/netbox-pathways/getting-started/configuration/)
- [Concepts](https://jsenecal.github.io/netbox-pathways/user-guide/concepts/)
- [QGIS Integration](https://jsenecal.github.io/netbox-pathways/user-guide/qgis-integration/)
- [Architecture](https://jsenecal.github.io/netbox-pathways/developer/architecture/)
- [GeoJSON API reference](https://jsenecal.github.io/netbox-pathways/reference/geojson-api/)

## Contributing

PRs welcome. Use conventional-commits PR titles (`feat:`, `fix:`, `chore:`, `docs:`, ...) -- release-drafter assembles release notes from them. Run `make setup` after cloning to install dev dependencies and the pre-commit hooks (including the AI-attribution-rejecting `commit-msg` hook).

## License

[Apache License 2.0](LICENSE).
