# Cable Routing

Cable routing connects NetBox's native `dcim.Cable` objects to the physical pathways they traverse. This is the core integration point between NetBox's device/cable inventory and Pathways' physical infrastructure documentation.

## Cable Segments

A **Cable Segment** represents one section of a cable's physical route through a single pathway. A cable's complete route is an ordered sequence of segments.

| Field | Description |
|-------|-------------|
| Cable | The NetBox `dcim.Cable` being routed |
| Pathway | The conduit, aerial span, or other pathway |
| Sequence | Order in the route (1, 2, 3...) |
| Enter Point | Geographic coordinate where the cable enters the pathway |
| Exit Point | Geographic coordinate where the cable exits |
| Slack Loop Location | Where extra cable is coiled |
| Slack Length | Extra cable length in meters |
| Lashed With | Other cable segments mechanically lashed together with this one on the same aerial span. Multi-select; symmetric. See [Aerial Overlashing](#aerial-overlashing) below. |

### Aerial Overlashing

In aerial plant, a fiber cable is sometimes mechanically lashed onto another cable rather than carrying its own support strand. Over time, an aerial span can accumulate a stack of cables all wrapped together by the same lash wire -- one cable installed, then a second lashed onto it, then a third onto that, and so on. From a load-and-handling perspective, all cables in that wrap share the same lashing.

The plugin captures this with **Lashed With**: a symmetric `ManyToManyField` between `CableSegment` instances. Adding a peer to one segment automatically adds this segment to the peer's `lashed_with` set -- there is no "host" or "guest" distinction. Each segment in the bundle is equally lashed with every other.

Lashing is per-segment, not per-cable, because a cable can be partly overlashed (aerial segments) and partly not (underground segments along the same route).

Note: `lashed_with` is **pairwise symmetric**, not transitive. If A is lashed with B and B is lashed with C, that does not automatically mean A is lashed with C -- the user must add each pair explicitly. The form's multi-select makes this fast: when adding a new cable segment to an existing bundle of N peers, select all N at once. A future enhancement could introduce a `LashingBundle` model to capture group identity directly; for now, the bundle is implicit in the graph.

To find every cable a given segment is lashed with: `segment.lashed_cables` (a `@property` returning a `Cable` queryset of every peer segment's cable).

If a peer cable is not modeled in NetBox (foreign plant, e.g. another carrier's cable), leave that peer out and record the relationship in the segment's `comments`.

### Example Route

A cable running from Building A to Building B might have this route:

| Seq | Pathway | Type | From | To |
|-----|---------|------|------|----|
| 1 | C-101 | Conduit | Bldg A Entrance | MH-001 |
| 2 | C-205 | Conduit | MH-001 | MH-002 |
| 3 | AS-010 | Aerial | MH-002 | Pole-15 |
| 4 | C-310 | Conduit | Pole-15 | Bldg B Entrance |

## Conduit Banks

Conduit banks organize the conduit openings on a structure. This is essential for field documentation — crews need to know exactly which opening to use.

### Bank Configuration

| Config | Layout | Total Conduits |
|--------|--------|----------------|
| 1x2 | 1 row, 2 columns | 2 |
| 1x3 | 1 row, 3 columns | 3 |
| 1x4 | 1 row, 4 columns | 4 |
| 2x2 | 2 rows, 2 columns | 4 |
| 2x3 | 2 rows, 3 columns | 6 |
| 3x3 | 3 rows, 3 columns | 9 |
| 3x4 | 3 rows, 4 columns | 12 |
| Custom | Irregular | Variable |

### Bank Positions

Conduits assigned to a bank get a **Bank Position** using a grid notation:

- Row letter + column number: `A1`, `A2`, `B1`, `B2`, etc.
- Row A is the top row, column 1 is the leftmost
- Each position in a bank is unique

### Encasement Types

| Type | Description |
|------|-------------|
| Concrete | Concrete-encased duct bank |
| Direct Buried | Duct bank buried without encasement |
| Bore | Horizontal directional drilling |
| Bridge Attachment | Attached to bridge structure |
| Tunnel | Inside a tunnel or utility corridor |

## Conduit Junctions

A conduit junction models a Y-tee where a branch conduit connects to a trunk conduit at a point along its span. Conduit endpoints can reference junctions instead of structures, enabling mid-span branching.

Key attributes:

- **Trunk Conduit** — The main conduit
- **Branch Conduit** — The branching conduit
- **Towards Structure** — Which end of the trunk the junction faces
- **Position on Trunk** — Normalized value (0.0 = start, 1.0 = end)

## Creating Cable Segments

1. Navigate to **Plugins > Pathways > Cable Segments**
2. Click **Add**
3. Select the **Cable** and **Pathway**
4. Set the **Sequence** number (determines route order)
5. Optionally set enter/exit points and slack details
6. Save and add more segments for the full route

!!! tip
    Maintain consistent sequence numbering. Gaps are fine (1, 2, 5, 10) but the order must reflect the physical cable route.

## Pull Sheets

Once cable segments are configured, the system can generate pull sheets — field documents showing the complete cable route. See [Pull Sheets](pull-sheets.md) for details.
