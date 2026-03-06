# Models

NetBox Pathways uses Django Multi-Table Inheritance (MTI) for pathway subtypes. The `Pathway` base model holds common fields, and each subtype (`Conduit`, `AerialSpan`, `DirectBuried`, `Innerduct`) adds type-specific fields.

## Structure

A physical structure in the cable plant — poles, manholes, cabinets, equipment rooms, etc.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Unique name |
| `structure_type` | ChoiceField | Type of structure (see below) |
| `site` | FK → dcim.Site | NetBox site |
| `location` | PointField | Geographic location (WGS84) |
| `elevation` | FloatField | Elevation in meters |
| `owner` | CharField | Structure owner/operator |
| `installation_date` | DateField | When the structure was installed |
| `access_notes` | TextField | Access restrictions or requirements |

**Structure Types:** Pole, Manhole, Handhole, Cabinet, Vault, Pedestal, Building Entrance, Splice Closure, Tower, Rooftop, Equipment Room, Telecom Closet, Riser Room

!!! note
    All choice fields allow blank values — field conditions are often unknown or undocumented in real-world plant data.

## Pathway (Base)

The base class for all pathway types. Contains geometry, endpoints, and capacity tracking.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Unique name |
| `pathway_type` | ChoiceField | Auto-set based on subtype (read-only) |
| `path` | LineStringField | Geographic path (WGS84) |
| `start_structure` | FK → Structure | Starting structure (optional) |
| `end_structure` | FK → Structure | Ending structure (optional) |
| `start_location` | FK → dcim.Location | Starting location (optional) |
| `end_location` | FK → dcim.Location | Ending location (optional) |
| `length` | FloatField | Total length in meters |
| `cable_count` | PositiveIntegerField | Current number of cables |
| `max_cable_count` | PositiveIntegerField | Maximum cable capacity |
| `installation_date` | DateField | When the pathway was installed |

**Endpoint Flexibility:** Each endpoint can be a Structure (outdoor) or a Location (indoor). This allows pathways to span from outdoor infrastructure into buildings and between indoor locations.

**Pathway Types:** Conduit, Aerial Span, Direct Buried, Innerduct, Microduct, Cable Tray, Raceway, Submarine

### Properties

- `start_endpoint` — Returns whichever start endpoint is set (structure or location)
- `end_endpoint` — Returns whichever end endpoint is set (structure or location)
- `utilization_percentage` — `(cable_count / max_cable_count) * 100`

## Conduit

A physical conduit (pipe/duct) between two points. Extends Pathway.

| Field | Type | Description |
|-------|------|-------------|
| `material` | ChoiceField | PVC, HDPE, Steel, Concrete, Fiberglass |
| `inner_diameter` | FloatField | Inner diameter in mm |
| `outer_diameter` | FloatField | Outer diameter in mm |
| `depth` | FloatField | Burial depth in meters |
| `conduit_bank` | FK → ConduitBank | Bank this conduit belongs to |
| `bank_position` | CharField | Position within the bank (e.g., A1, B2) |
| `start_junction` | FK → ConduitJunction | Start at a junction (alternative to structure/location) |
| `end_junction` | FK → ConduitJunction | End at a junction (alternative to structure/location) |

**Endpoint Validation:** Each end of a conduit must be exactly one of: a Structure, a Location, or a ConduitJunction. Having more than one or none raises a validation error.

**Bank Position Uniqueness:** Only one conduit can occupy a given position within a conduit bank (enforced by a conditional unique constraint).

## Aerial Span

An aerial pathway between structures (poles, towers, buildings). Extends Pathway.

| Field | Type | Description |
|-------|------|-------------|
| `aerial_type` | ChoiceField | Messenger Wire, Self-Supporting, Lashed, Wrapped, ADSS |
| `attachment_height` | FloatField | Height in meters |
| `sag` | FloatField | Cable sag in meters |
| `messenger_size` | CharField | Messenger wire size/type |
| `wind_loading` | CharField | Wind loading zone/rating |
| `ice_loading` | CharField | Ice loading zone/rating |

## Direct Buried

A cable path buried directly in the ground without conduit. Extends Pathway.

| Field | Type | Description |
|-------|------|-------------|
| `burial_depth` | FloatField | Depth in meters |
| `warning_tape` | BooleanField | Warning tape installed above cable |
| `tracer_wire` | BooleanField | Tracer wire installed with cable |
| `armor_type` | CharField | Cable armor type |

## Innerduct

A smaller duct inside a parent conduit. Extends Pathway.

| Field | Type | Description |
|-------|------|-------------|
| `parent_conduit` | FK → Conduit | The conduit this innerduct lives inside |
| `size` | CharField | Size (e.g., 1.25", 32mm) |
| `color` | CharField | Color for identification |
| `position` | CharField | Position within parent conduit |

When created without explicit start/end endpoints, an innerduct inherits its parent conduit's endpoints automatically.

## Conduit Bank

A group of conduit openings on one side or wall of a structure (e.g., a manhole wall).

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Unique name |
| `structure` | FK → Structure | The structure this bank belongs to |
| `configuration` | ChoiceField | Layout (1x2, 2x2, 3x3, etc.) or Custom |
| `total_conduits` | PositiveIntegerField | Total conduit positions |
| `encasement_type` | ChoiceField | Concrete Encased, Direct Buried, Directional Bore, Bridge Attachment, Tunnel |
| `installation_date` | DateField | When the bank was installed |

!!! info "Domain Note"
    A conduit bank belongs to a **single structure** — it represents the conduit openings on one wall/side of that structure. Individual conduits within a bank each have their own independent start/end destinations. Configurations can be irregular (use "Custom" configuration).

## Conduit Junction

A Y-shaped tee on a trunk conduit mid-span, where a branch conduit connects.

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField | Unique name |
| `trunk_conduit` | FK → Conduit | The main conduit being teed |
| `branch_conduit` | FK → Conduit | The branch conduit |
| `towards_structure` | FK → Structure | Which end of the trunk the junction faces |
| `position_on_trunk` | FloatField | Position along trunk (0.0 = start, 1.0 = end) |

**Validation:** `towards_structure` must be one of the trunk conduit's endpoints.

The junction's geographic `location` property is computed by interpolating along the trunk conduit's path geometry.

## Pathway Location

Records that a pathway passes through a specific location or site along its length — ordered waypoints between the start and end endpoints.

| Field | Type | Description |
|-------|------|-------------|
| `pathway` | FK → Pathway | The pathway |
| `site` | FK → dcim.Site | Site waypoint (optional) |
| `location` | FK → dcim.Location | Location waypoint (optional) |
| `sequence` | PositiveIntegerField | Order along the pathway |

At least one of `site` or `location` is required per waypoint. Sequence is unique per pathway.

## Cable Segment

Links a NetBox `dcim.Cable` to a pathway, recording that the cable passes through that pathway as part of its route.

| Field | Type | Description |
|-------|------|-------------|
| `cable` | FK → dcim.Cable | The cable being routed |
| `pathway` | FK → Pathway | The pathway segment |
| `sequence` | PositiveIntegerField | Order in the cable's route |
| `enter_point` | PointField | Entry point to the pathway |
| `exit_point` | PointField | Exit point from the pathway |
| `slack_loop_location` | PointField | Location of slack loop |
| `slack_length` | FloatField | Length of slack in meters |

The sequence is unique per cable — each cable has an ordered list of pathway segments it traverses. This data drives the [Pull Sheet](pull-sheets.md) feature.
