# Pathways

Pathways represent the physical routes that cables follow between structures and locations. Each pathway has a LineString geometry defining its geographic path.

## Pathway Types

### Conduit

A pipe or duct that cables are pulled through. Conduits are the most common pathway type for underground infrastructure.

| Field | Description |
|-------|-------------|
| Material | PVC, HDPE, Steel, Concrete, Fiberglass |
| Inner Diameter | Inside diameter in millimeters |
| Outer Diameter | Outside diameter in millimeters |
| Depth | Burial depth in meters |
| Conduit Bank | Optional bank assignment at a structure |
| Bank Position | Position within the bank (e.g., `A1`, `B2`) |
| Start/End Junction | Optional junction endpoint (instead of structure) |

### Aerial Span

An overhead route, typically between poles.

| Field | Description |
|-------|-------------|
| Aerial Type | Messenger, Self-support, Lashed, Wrapped, ADSS |
| Attachment Height | Height of cable attachment in meters |
| Sag | Maximum sag in meters |
| Messenger Size | Messenger wire specification |
| Wind Loading | Wind loading specification |
| Ice Loading | Ice loading specification |

### Direct Buried

A cable path buried directly in the ground without a conduit.

| Field | Description |
|-------|-------------|
| Burial Depth | Depth in meters |
| Warning Tape | Whether warning tape is installed |
| Tracer Wire | Whether tracer wire is installed |
| Armor Type | Cable armor specification |

### Innerduct

A smaller duct installed inside a parent conduit to subdivide capacity.

| Field | Description |
|-------|-------------|
| Parent Conduit | The conduit this innerduct is inside |
| Size | Innerduct size (e.g., `1.25"`, `32mm`) |
| Color | Innerduct color for identification |
| Position | Position within the parent conduit |

Innerducts inherit start and end structures from their parent conduit if not explicitly set.

## Endpoints

Every pathway has a start endpoint and an end endpoint. These can be:

- **Structure** — An outdoor structure (pole, manhole, etc.)
- **Location** — An indoor NetBox location (room, floor)
- **Junction** — A conduit junction (conduits only)

You can mix endpoint types. For example, a conduit starting at a manhole (structure) and ending at an equipment room (location) models a building entrance path.

## Creating a Pathway

1. Navigate to the appropriate pathway list (e.g., **Plugins > Pathways > Conduits**)
2. Click **Add**
3. Set the name, endpoints, and type-specific fields
4. Draw the path on the map widget or enter geometry manually
5. Save

!!! tip
    The map widget snaps to nearby structures when drawing paths. Start and end your line near your selected structures for accurate geometry.

## Pathway on the Map

On the interactive map, pathways render as colored lines:

| Type | Line Style | Color |
|------|------------|-------|
| Conduit | Solid | Brown |
| Aerial Span | Dashed | Blue |
| Direct Buried | Dotted | Gray |
| Innerduct | Solid (thin) | Orange |
| Cable Tray | Solid | Green |
| Raceway | Solid | Indigo |

Clicking a pathway line opens the sidebar with details including endpoints, length, type-specific attributes, and routed cables.

## Lifecycle

Every pathway carries the following lifecycle fields, in addition to the type-specific fields above:

| Field | Description |
|-------|-------------|
| Installation Date | When the pathway was physically installed |
| Commissioned Date | When the pathway was commissioned / accepted (often after the install date for outside-plant work) |
| Tenant | Tenant served by / customer assigned to this pathway |
| Installed By | Tenant entry for the contractor or workforce that physically installed the pathway (distinct from `Tenant`) |

## Filtering

Pathway lists support filtering by:

- **Pathway Type** -- Conduit, Aerial, Direct Buried, etc.
- **Start/End Structure** -- Filter by connected structures
- **Site** -- Filter by associated site
- **Material** -- Conduit material (conduits only)
- **Tenant** -- Filter by owning tenant (served customer)
- **Installed By** -- Filter by installer/contractor tenant
- **Installation Date** / **Commissioned Date** -- Filter by date
- **Has Path** -- Filter pathways with/without geometry

## Intermediate Locations

Pathways can pass through intermediate locations (sites or rooms) along their route. Use **Pathway Locations** to record these waypoints with sequence numbers for ordering. This is useful for documenting that a conduit passes through multiple manholes along its route.
