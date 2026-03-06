# NetBox Pathways

A NetBox plugin for documenting physical cable plant infrastructure with PostGIS integration. Track conduits, aerial spans, structures, and cable routing with geographic data — comparable to SmallWorld or ArcGIS with ArcFM for outside/inside plant documentation.

## Features

- **Structures** — Poles, manholes, cabinets, equipment rooms, and more with PostGIS point geometry
- **Pathways** — Conduits, aerial spans, direct buried, innerducts, cable trays with PostGIS line geometry
- **Conduit Banks & Junctions** — Model conduit bank configurations and mid-span Y-tees
- **Cable Routing** — Track which NetBox cables traverse which pathways, in sequence
- **Pull Sheets** — Printable cable routing documents for field crews
- **GeoJSON API** — Standard GeoJSON endpoints for QGIS and other GIS clients
- **QGIS Integration** — Style files, project generator, and documentation
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
```

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
