# Conduit Junctions

A **Conduit Junction** records a Y-tee where a branch conduit joins a
trunk conduit at an intermediate point along the trunk's path, rather than
at one of the trunk's structure endpoints. Junctions are how the data
model represents mid-span tees, lateral entries, and similar in-line
splice locations without a manhole.

## When To Use A Junction

A junction is appropriate when:

- A conduit physically branches off another conduit between two
  structures.
- There is no manhole, handhole, or other Structure at the branch point.
- You still need to record where the branch attaches and which way it
  faces.

If a manhole or handhole exists at the branch point, model that as a
Structure instead and connect the conduits to it normally. Structures are
first-class endpoints; junctions are an escape hatch for the cases where
a Structure does not physically exist.

## Fields

| Field                | Type           | Notes                                                                  |
|----------------------|----------------|------------------------------------------------------------------------|
| `label`              | string         | Optional human label.                                                  |
| `trunk_conduit`      | FK Conduit     | The main conduit being tapped.                                         |
| `branch_conduit`     | FK Conduit     | The conduit branching off.                                             |
| `towards_structure`  | FK Structure   | Which end of the trunk the junction faces.                             |
| `position_on_trunk`  | float `[0, 1]` | Normalised position. `0.0` is the trunk start, `1.0` is the trunk end. |

`towards_structure` must be one of the trunk's two structure endpoints. If
the trunk uses location or junction endpoints (no Structure on either
side) you cannot set this field; trying to do so raises
`ValidationError`.

## How The Branch Conduit Connects

The `branch_conduit` references the junction by setting one of its
endpoints to that junction (`start_junction` or `end_junction`). Each
conduit endpoint is one and only one of:

- a `start_structure` / `end_structure`, or
- a `start_location` / `end_location`, or
- a `start_junction` / `end_junction`.

`Conduit.clean()` enforces "exactly one" on each side. The junction's
location is computed from the trunk's geometry at
`position_on_trunk` (using `LineString.interpolate_normalized`), and the
branch's path is snapped to that point within 1 metre tolerance.

## Position On Trunk

`position_on_trunk` is a normalised distance, not absolute meters:

| `position_on_trunk` | Meaning                                |
|---------------------|----------------------------------------|
| `0.0`               | At the trunk's start endpoint.         |
| `0.5`               | Halfway along the trunk.               |
| `1.0`               | At the trunk's end endpoint.           |

The pair `(trunk_conduit, position_on_trunk)` is unique. To put two
junctions at exactly the same point you would have to nudge one of the
positions slightly (for example `0.499` vs `0.501`). In practice this is
rarely needed.

The junction's geographic location is derived, not stored. If the trunk's
`path` geometry is moved, the junction follows.

## Constraints At A Glance

- `towards_structure` must be one of the trunk's structure endpoints.
- `position_on_trunk` must be in `[0.0, 1.0]`.
- The combination of `(trunk_conduit, position_on_trunk)` is unique.
- Trying to set `towards_structure` on a trunk with no structure
  endpoints raises a validation error.

## Workflow

1. Create the trunk conduit between two structures.
2. Create the junction, picking a `position_on_trunk` (e.g. `0.4`) and
   setting `towards_structure` to whichever trunk endpoint the branch
   faces.
3. Create the branch conduit. Set `start_junction` (or `end_junction`)
   to the new junction. Set the other endpoint to the structure or
   location where the branch terminates.
4. Draw the branch conduit's path. The endpoint touching the junction
   will snap onto the trunk geometry within 1 metre tolerance; outside
   that, the form returns a validation error.

## Cable Routing Through Junctions

A conduit junction is not itself a routable pathway. When tracing a cable
through the network, the route follows trunk and branch conduits;
junctions are joining points that allow the route to switch from trunk
to branch (or vice versa). The route planner and the cable trace
endpoint both understand junction adjacency automatically.
