# NetBox Pathways

A NetBox plugin for documenting physical cable plant infrastructure with PostGIS integration. Track conduits, aerial spans, structures, and cable routing with geographic data — comparable to SmallWorld or ArcGIS with ArcFM for outside/inside plant documentation.

## Features

- **Structures** — Poles, manholes, cabinets, equipment rooms, and more with PostGIS geometry (point or polygon)
- **Pathways** — Conduits, aerial spans, direct buried, innerducts, cable trays with PostGIS line geometry
- **Conduit Banks & Junctions** — Model conduit bank configurations and mid-span Y-tees
- **Cable Routing** — Track which NetBox cables traverse which pathways, in sequence
- **Pull Sheets** — Printable cable routing documents for field crews
- **GeoJSON API** — Standard GeoJSON endpoints for QGIS and other GIS clients
- **QGIS Integration** — Style files, project generator, and documentation
- **Geometry Editing** — Draw and edit geometries directly in NetBox forms via Leaflet map widgets
- **Interactive Map** — Built-in Leaflet map for quick visualization
- **Indoor/Outdoor** — Pathways can terminate at structures (outdoor) or NetBox locations (indoor)

## Requirements

| Component | Version |
|-----------|---------|
| NetBox | 4.5.3+ |
| Python | 3.12+ |
| PostgreSQL | 16+ with PostGIS 3.4 |

## Installation

```bash
pip install netbox-pathways
```

Add to your NetBox `configuration.py`:

```python
PLUGINS = ['netbox_pathways']

PLUGINS_CONFIG = {
    'netbox_pathways': {
        'srid': 3348,           # REQUIRED — your EPSG code (see warning below)
        'map_center_lat': 45.5, # default map center latitude (optional)
        'map_center_lon': -73.5,# default map center longitude (optional)
        'map_zoom': 10,         # default map zoom level (optional)
    }
}
```

> **⚠️ WARNING: SRID IS IMMUTABLE AFTER INSTALLATION ⚠️**
>
> The `srid` setting defines the coordinate reference system used for **all** geometry
> columns in the database. It is baked into the database schema at migration time.
>
> **Changing the SRID after data has been loaded WILL CORRUPT YOUR SPATIAL DATA.**
> PostgreSQL/PostGIS does NOT automatically re-project existing coordinates when the
> column SRID changes. Your geometries will have wrong coordinates in the new CRS
> with no way to recover them automatically.
>
> **Choose your SRID carefully before first deployment.** Common choices:
> - `4326` — WGS84, GPS coordinates (degrees). Global, but distorts distances/areas.
> - `3857` — Web Mercator (meters). Used by Google Maps, OSM tiles.
> - `3348` — NAD83(CSRS) / Statistics Canada Lambert (meters). Good for Canada.
> - `2154` — RGF93 / Lambert-93 (meters). Good for France.
> - `32632` — WGS84 / UTM zone 32N (meters). Good for central Europe.
>
> If you need to change SRID after deployment, you must manually re-project all
> geometry data using PostGIS `ST_Transform()` and update the column SRID definitions.
> This is an advanced DBA operation — back up everything first.

Run migrations and restart:

```bash
cd /opt/netbox/netbox
python manage.py migrate
python manage.py collectstatic --no-input
sudo systemctl restart netbox netbox-rq
```

## QGIS Quick Start

Generate a QGIS project with all layers pre-configured:

```bash
python manage.py generate_qgis_project \
  --url https://your-netbox \
  --token your-api-token
```

Open the generated `.qgs` file in QGIS.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/api/plugins/pathways/structures/` | Structures (CRUD) |
| `/api/plugins/pathways/conduits/` | Conduits (CRUD) |
| `/api/plugins/pathways/aerial-spans/` | Aerial spans (CRUD) |
| `/api/plugins/pathways/geo/structures/` | GeoJSON structures |
| `/api/plugins/pathways/geo/pathways/` | GeoJSON pathways |

See the [full documentation](https://jsenecal.github.io/netbox-pathways/) for all endpoints.

## Documentation

Full documentation is available at **[jsenecal.github.io/netbox-pathways](https://jsenecal.github.io/netbox-pathways/)** or can be built locally:

```bash
pip install mkdocs mkdocs-material
mkdocs serve
```

## License

Apache 2.0 License
