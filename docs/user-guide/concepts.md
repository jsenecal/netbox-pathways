# Concepts

This page explains the core data model and how the different components of NetBox Pathways relate to each other.

## Data Model Overview

```mermaid
erDiagram
    Structure ||--o{ Pathway : "start/end"
    Structure ||--o{ ConduitBank : contains
    Structure ||--o{ ConduitJunction : "towards"
    Pathway ||--o{ CableSegment : routes
    Pathway ||--|{ PathwayLocation : "passes through"
    Cable ||--o{ CableSegment : "routed via"
    ConduitBank ||--o{ Conduit : positions
    Conduit ||--o{ Innerduct : contains
    Conduit ||--o{ ConduitJunction : "branches at"
    Pathway <|-- Conduit : extends
    Pathway <|-- AerialSpan : extends
    Pathway <|-- DirectBuried : extends
    Pathway <|-- Innerduct : extends
```

## Structures

A **Structure** is any physical location where cables can enter, exit, or transition between pathway types. Structures have geographic coordinates (Point or Polygon geometry) and belong to a NetBox Site.

| Category | Types |
|----------|-------|
| **Outdoor** | Pole, Manhole, Handhole, Cabinet, Vault, Pedestal, Splice Closure, Tower, Roof |
| **Indoor** | Equipment Room, Telecom Closet, Riser Room, Building Entrance |

Structures serve as endpoints for Pathways and anchor points for Conduit Banks.

## Pathways

A **Pathway** is a physical route between two endpoints. It has a LineString geometry (the geographic path) and connects structures, locations, or junctions.

Pathways use multi-table inheritance with four subtypes:

| Subtype | Description | Key Fields |
|---------|-------------|------------|
| **Conduit** | Pipe or duct | Material, diameter, depth, bank position |
| **Aerial Span** | Overhead route | Attachment height, sag, messenger, wind/ice loading |
| **Direct Buried** | Underground without conduit | Burial depth, warning tape, tracer wire, armor |
| **Innerduct** | Smaller duct inside a conduit | Parent conduit, size, color, position |

### Endpoint Flexibility

Pathways support flexible endpoints to model both outdoor and indoor infrastructure:

- **Structure** — A pole, manhole, or other physical structure
- **Location** — A NetBox `dcim.Location` (room, floor, wing)
- **Junction** — A conduit junction (Y-tee) for conduit subtypes only

Each pathway has exactly one start endpoint and one end endpoint. These can be different types (e.g., a conduit starting at a manhole and ending at a building location).

## Conduit Banks

A **Conduit Bank** represents a group of conduit openings on one side of a structure — typically a wall in a manhole or handhole. Banks have a configuration (e.g., 2x3 for 2 rows by 3 columns) and track the total number of openings.

Individual Conduits are assigned to a bank with a **Bank Position** (e.g., `A1`, `B2`). Each position within a bank is unique.

!!! note
    A Conduit Bank belongs to a single structure. The conduits that pass through a bank each have their own start and end points — they are not constrained to connect the same pair of structures.

## Conduit Junctions

A **Conduit Junction** models a Y-tee where a branch conduit meets a trunk conduit at a point along its span. Key attributes:

- **Trunk Conduit** — The main conduit being tapped
- **Branch Conduit** — The conduit branching off
- **Towards Structure** — Which end of the trunk the junction faces
- **Position on Trunk** — Normalized position (0.0 to 1.0) along the trunk

The junction's geographic location is interpolated from the trunk conduit's path geometry.

## Cable Segments

A **Cable Segment** links a NetBox `dcim.Cable` to a Pathway. Multiple segments trace a cable's complete physical route:

| Field | Description |
|-------|-------------|
| **Cable** | The NetBox cable being routed |
| **Pathway** | Which pathway this segment traverses |
| **Sequence** | Order of this segment in the route (1, 2, 3...) |
| **Enter/Exit Points** | Geographic coordinates where the cable enters and exits the pathway |
| **Slack Length** | Extra cable length stored at this segment |

Cable segments ordered by sequence form a complete **pull sheet** for field crews.

## Pathway Locations

A **Pathway Location** records intermediate waypoints along a pathway's route — locations the pathway passes through between its start and end. Each waypoint references a NetBox Site or Location and has a sequence number for ordering.

## Site Geometry

A **Site Geometry** links a NetBox Site to the Pathways geospatial system. It can hold an explicit geometry or fall back to a linked Structure's location. This model enables external plugins to reference Site-based geometry through the [Map Layer Registry](../developer/map-layer-registry.md).

## Relationship to NetBox Core

NetBox Pathways integrates with several core NetBox models:

| NetBox Model | Relationship |
|-------------|--------------|
| `dcim.Site` | Structures belong to Sites; PathwayLocations reference Sites |
| `dcim.Location` | Pathway endpoints can be Locations (indoor routing) |
| `dcim.Cable` | CableSegments link Cables to Pathways |
| `tenancy.Tenant` | Structures, Pathways, and Conduit Banks support tenant assignment |
