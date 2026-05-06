# Structures

Structures are the anchor points of your cable plant. Every pathway starts and ends at a structure (or indoor location), and structures host conduit banks, equipment, and cable transitions.

## Structure Types

| Type | Icon Shape | Color | Typical Use |
|------|------------|-------|-------------|
| Pole | Circle outline | Green | Aerial cable attachment |
| Manhole | Circle filled | Blue | Underground access, large |
| Handhole | Circle outline | Cyan | Underground access, small |
| Cabinet | Square rounded | Orange | Street-level enclosure |
| Vault | Square filled | Purple | Underground concrete vault |
| Pedestal | Square outline | Yellow | Above-ground distribution |
| Building Entrance | Square dot | Red | Cable entry to building |
| Splice Closure | Circle dot | Brown | Inline splice housing |
| Tower | Crosshair | Dark Red | Communication tower |
| Roof | Triangle | Gray | Rooftop mount |
| Equipment Room | Square outline | Teal | Indoor telecom room |
| Telecom Closet | Diamond | Indigo | Indoor wiring closet |
| Riser Room | Diamond outline | Pink | Vertical cable transition |

## Creating a Structure

1. Navigate to **Plugins > Pathways > Structures**
2. Click **Add**
3. Fill in the fields:

| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Unique identifier (e.g., `MH-001`, `POLE-042`) |
| Status | No | Lifecycle state: `Planned`, `Active`, `Under Construction`, `Decommissioning`, `Retired`, or `Abandoned in place` (still physically present, no longer in service) |
| Structure Type | No | Type from the table above |
| Site | No | NetBox site this structure belongs to |
| Location | Yes | Geographic point or polygon -- click the map or enter coordinates |
| Elevation | No | Elevation in meters |
| Dimensions | No | Height, width, length, depth in meters |
| Installation Date | No | When the structure was physically installed |
| Commissioned Date | No | When the structure was commissioned / handed over (often after the install date for outside-plant work) |
| Tenant | No | Tenant served by / customer assigned to this structure |
| Installed By | No | Tenant entry for the contractor or workforce that physically installed the structure (distinct from `Tenant`) |
| Access Notes | No | Instructions for field crews (e.g., "Key #42, contact dispatch") |

## Location Geometry

Structure locations can be either a **Point** (lat/lon) or a **Polygon** (footprint). The map and GIS tools use the structure's centroid for marker placement regardless of geometry type.

The location picker on the form supports:

- **Click to place** — Click the map to set a point
- **Draw polygon** — Use polygon draw tools for building footprints
- **Manual entry** — Enter WKT or coordinates directly

## Structures on the Map

On the interactive map, structures appear as markers with shapes and colors matching their type (see table above). Clicking a structure marker opens the sidebar detail panel with:

- Structure name and type
- Site assignment
- Dimensions and elevation
- Connected pathways
- Associated conduit banks

## Filtering

The structure list supports filtering by:

- **Site** -- Filter by NetBox site
- **Structure Type** -- Filter by type (pole, manhole, etc.)
- **Status** -- Filter by lifecycle state (including `Abandoned in place`)
- **Tenant** -- Filter by owning tenant (served customer)
- **Installed By** -- Filter by installer/contractor tenant
- **Installation Date** / **Commissioned Date** -- Filter by date
- **Has Location** -- Filter structures with/without coordinates

## Conduit Banks

Each structure can have one or more conduit banks. A conduit bank represents a wall or face of the structure with conduit openings. See [Cable Routing](cable-routing.md) for details on bank configuration and conduit positioning.

## Bulk Operations

The structure list view supports bulk editing and deletion. Select multiple structures using the checkboxes, then use the toolbar actions to:

- Assign to a site
- Change structure type
- Assign a tenant
- Delete selected structures
