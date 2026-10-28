# Conduit Banks

A **Conduit Bank** is an encased group of conduits that share a single
physical route between two structures. It is a pathway of type
`conduit_bank`; its conduits are pathways of type `conduit` whose `parent` is
the bank. On the map the bank is what gets drawn; the conduits inside it are
detail records visible on the bank's detail page and in the cable routing UI.

This page focuses on banks specifically. For routing cables through banks
and individual conduits, see [Cable Routing](cable-routing.md).

## When To Model A Bank Versus Standalone Conduits

| Use a bank when                                                    | Use standalone conduits when                       |
|--------------------------------------------------------------------|----------------------------------------------------|
| Multiple conduits share an excavation, encasement, or duct rack.   | A single conduit runs between two structures.      |
| You need to record a configuration like 2x2 or 3x3.                | The conduit is in a different trench than its peers.|
| You want the map to show one feature, not N parallel lines.        | You need to draw distinct paths per conduit.       |

A conduit has at most one parent: a conduit bank or a raceway. Clearing a
conduit's `parent` makes it a top-level conduit, which the map draws on its
own.

## Bank Fields

| Field             | Type        | Notes                                                            |
|-------------------|-------------|------------------------------------------------------------------|
| `label`           | string      | Common pathway field. Optional but strongly recommended.         |
| `geometry`        | LineString  | The geographic route of the bank. Drawn on the map widget.       |
| `start_structure` | FK          | First end of the bank. Required at one of structure or location. |
| `end_structure`   | FK          | Second end of the bank.                                          |
| `start_face`      | choice      | Which face of the start structure (north/south/east/west/other). |
| `end_face`        | choice      | Which face of the end structure.                                 |
| `configuration`   | choice      | Layout shape, see table below. Leave blank if irregular.         |
| `total_conduits`  | int         | Designed capacity in slots. May be more than the actual count.   |
| `height`          | int         | Number of duct rows (vertical count). Optional, nullable.        |
| `width`           | int         | Number of duct columns (horizontal count). Optional, nullable.   |
| `encasement_type` | choice      | Concrete, direct buried, bore, bridge attachment, tunnel.        |

The bank has the rest of the common pathway fields (tenant, length,
installation date, comments). A bank is always top-level: it cannot have a
parent.

### Configuration Choices

| Value    | Layout              | Total conduits |
|----------|---------------------|----------------|
| `1x2`    | 1 row x 2 columns    | 2              |
| `1x3`    | 1 row x 3 columns    | 3              |
| `1x4`    | 1 row x 4 columns    | 4              |
| `2x2`    | 2 rows x 2 columns   | 4              |
| `2x3`    | 2 rows x 3 columns   | 6              |
| `3x3`    | 3 rows x 3 columns   | 9              |
| `3x4`    | 3 rows x 4 columns   | 12             |
| `custom` | Irregular layout     | Variable       |

`total_conduits` is a separate field because real installations often
provide spare capacity beyond what the named configuration implies, or use
non-grid layouts described as `custom`.

### Encasement Types

| Value               | Description                                  |
|---------------------|----------------------------------------------|
| `concrete`          | Concrete-encased duct bank.                  |
| `direct_buried`     | Buried without concrete jacket.              |
| `bore`              | Pulled through a directional bore.           |
| `bridge_attachment` | Attached to bridge or other span structure.  |
| `tunnel`            | Inside a tunnel or shared utility corridor.  |

## Position Of Conduits In A Bank

Conduits inside a bank carry a `position` like `A1` or `B3`:

- Row letter (`A`, `B`, ...) names the row, with `A` as the top.
- Column number (`1`, `2`, ...) names the column, with `1` on the left.
- The combination of `(parent, position)` is unique among conduits. The
  database enforces this with a partial unique constraint when both fields
  are populated. Innerduct positions are not unique.

Position is a free-text field, so you can use any naming you like
(`L-1`, `R-2`, `slot-3a`). Stay consistent inside one organisation.

## Map Behaviour

A bank renders as a single LineString on the interactive map and on
exported QGIS layers. The conduits inside it, and their innerducts, do not
appear as separate features: the map requests
`/api/plugins/pathways/geo/pathways/?pathway_type=<type>&containers=true`,
which returns only top-level drawn pathways. The Map button of a conduit or
innerduct in the bank, `?select=` and map search all land on the bank.

To inspect the conduits inside a bank, open the bank detail page in NetBox
and use the Children panel, or the Contents tab for everything inside it at
any depth.

## Adding conduits to a bank

The Children panel on a conduit bank's detail page has an Add button that
opens the pathway form with the type set to conduit, the parent set to the
bank, and the bank's start/end structures or locations, faces, installer,
and dates pre-filled. Adjust anything before saving; every value is a plain
form field.

Endpoints may also be left blank: a conduit that belongs to a bank
inherits the bank's endpoints when it is saved, the same way any child
inherits from its parent. Conduits inside a bank never need their own
geometry -- the bank owns the route -- and the bank is the feature drawn on
the map.

If a conduit has no tenant of its own, tables show the bank's tenant
marked with `*`, following the NetBox convention for inherited tenancy.
Assign a tenant on the conduit itself to override it.

## Validation

Bank endpoints follow the same rules as any pathway:

- Exactly one start endpoint (structure or location).
- Exactly one end endpoint (structure or location).
- The `geometry` LineString must start and end within 1 metre of the
  configured structure geometries. The plugin snaps within tolerance and
  raises `ValidationError` outside it.

Junctions are not valid endpoints for a bank. Banks always run between two
structures or locations.

## Deleting A Bank

A bank that still contains conduits cannot be deleted: `parent` is a
protected relation, so NetBox shows the protected-object message (the REST
API returns `409 Conflict`) listing the conduits. Clear the conduits'
`parent` or delete them first, then delete the bank.
