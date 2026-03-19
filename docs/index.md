# NetBox Pathways

**Physical cable plant infrastructure documentation for NetBox.**

NetBox Pathways extends [NetBox](https://netbox.dev/) with comprehensive outside and inside plant documentation — structures, pathways, conduit systems, cable routing, and GIS integration. Think SmallWorld or ArcGIS with ArcFM, but integrated directly into your network source of truth.

---

## Key Features

<div class="grid cards" markdown>

-   :material-map-marker:{ .lg .middle } **Structures**

    ---

    Document poles, manholes, cabinets, equipment rooms, and other infrastructure with full geographic coordinates and metadata.

    [:octicons-arrow-right-24: Structures](user-guide/structures.md)

-   :material-transit-connection-variant:{ .lg .middle } **Pathways**

    ---

    Model conduits, aerial spans, direct buried routes, innerducts, cable trays, and raceways connecting your structures.

    [:octicons-arrow-right-24: Pathways](user-guide/pathways.md)

-   :material-cable-data:{ .lg .middle } **Cable Routing**

    ---

    Track which cables run through which pathways with entry/exit points, sequencing, and slack loop documentation.

    [:octicons-arrow-right-24: Cable Routing](user-guide/cable-routing.md)

-   :material-map:{ .lg .middle } **Interactive Map**

    ---

    Leaflet-based map with structure markers, pathway lines, layer toggles, search, filtering, and hover details.

    [:octicons-arrow-right-24: Interactive Map](user-guide/interactive-map.md)

-   :material-printer:{ .lg .middle } **Pull Sheets**

    ---

    Generate field crew documents showing cable routing through pathways with lengths and slack requirements.

    [:octicons-arrow-right-24: Pull Sheets](user-guide/pull-sheets.md)

-   :material-earth:{ .lg .middle } **GIS Integration**

    ---

    GeoJSON REST API endpoints plus QGIS project generator for seamless GIS client integration.

    [:octicons-arrow-right-24: QGIS Integration](user-guide/qgis-integration.md)

-   :material-puzzle:{ .lg .middle } **Plugin Extensibility**

    ---

    Map layer registry allows other NetBox plugins to display their data on the Pathways map.

    [:octicons-arrow-right-24: Map Layer Registry](developer/map-layer-registry.md)

</div>

---

## Plugin Scope

NetBox Pathways handles **physical infrastructure** — where cables physically go. It does not handle splice connections, cable internals, or fiber strand management. Those capabilities are planned for a separate splice/connectivity plugin.

The boundary is NetBox's native `dcim.Cable` model: Pathways tracks physical routing; the splice plugin tracks what's inside cables and how strands connect.

---

## Requirements

| Component    | Version                         |
|--------------|---------------------------------|
| NetBox       | 4.5.3+                         |
| Python       | 3.12+                          |
| PostgreSQL   | 16+ with PostGIS 3.4           |
| Django       | 5.2+ (ships with NetBox 4.5)   |
| GDAL/GEOS   | System libraries for PostGIS   |

---

## Quick Start

```bash
pip install netbox-pathways
```

Then add to your NetBox configuration:

```python
PLUGINS = ['netbox_pathways']
```

See the [Installation Guide](getting-started/installation.md) for full setup instructions.
