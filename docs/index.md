# NetBox Pathways

A NetBox plugin for documenting physical cable plant infrastructure — comparable to SmallWorld or ArcGIS with ArcFM for outside/inside plant documentation.

NetBox Pathways tracks **where cables physically go**: the structures they pass through, the conduits and aerial spans they traverse, and the geographic paths they follow. It integrates with PostGIS for spatial data and provides GeoJSON API endpoints for QGIS and other GIS clients.

## What It Does

- **Structures** — Poles, manholes, handholes, cabinets, building entrances, equipment rooms, telecom closets, riser rooms
- **Pathways** — Conduits, aerial spans, direct buried paths, innerducts, cable trays, raceways
- **Conduit Banks** — Groups of conduit openings on a structure wall, with position tracking
- **Conduit Junctions** — Y-tees where conduits branch mid-span
- **Cable Segment Routing** — Track which NetBox cables pass through which pathways, in what order
- **Pull Sheets** — Printable documents showing complete cable routing for field crews
- **GIS Integration** — GeoJSON API endpoints for QGIS, with style files and project generator
- **Interactive Map** — Leaflet-based map view of structures and pathways

## Plugin Scope

NetBox Pathways handles physical infrastructure routing only. It does **not** cover:

- Splice connections (fusion, mechanical, connectorized)
- Cable internals (fiber type, buffer colors, strand details)
- End-to-end circuit tracing
- OTDR/test results

These are planned for a separate splice/connectivity plugin. The boundary between the two plugins is NetBox's native `dcim.Cable` model — Pathways tracks physical routing, the splice plugin will track what's inside cables and how strands connect.

## Requirements

| Component | Version |
|-----------|---------|
| NetBox | 4.5.3+ |
| Python | 3.12+ |
| PostgreSQL | 16+ with PostGIS 3.4 |
| Django | 5.2+ (included with NetBox) |

## Quick Start

```bash
pip install netbox-pathways
```

Then add to your NetBox configuration:

```python
PLUGINS = ['netbox_pathways']
```

See [Installation](installation.md) for full setup instructions.
