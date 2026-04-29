# Conduit Banks

A **Conduit Bank** is an encased group of conduits that share a single
physical route between two structures. On the map the bank is what gets
drawn; the conduits inside it are detail records visible only on the bank's
detail page and in the cable routing UI.

This page focuses on banks specifically. For routing cables through banks
and individual conduits, see [Cable Routing](cable-routing.md).

## When To Model A Bank Versus Standalone Conduits

| Use a bank when                                                    | Use standalone conduits when                       |
|--------------------------------------------------------------------|----------------------------------------------------|
| Multiple conduits share an excavation, encasement, or duct rack.   | A single conduit runs between two structures.      |
| You need to record a configuration like 2x2 or 3x3.                | The conduit is in a different trench than its peers.|
| You want the map to show one feature, not N parallel lines.        | You need to draw distinct paths per conduit.       |

A conduit may belong to at most one bank. Removing the `conduit_bank`
foreign key promotes that conduit back to a map-visible feature.

## Bank Fields

| Field             | Type        | Notes                                                            |
|-------------------|-------------|------------------------------------------------------------------|
| `label`           | string      | Inherited from `Pathway`. Optional but strongly recommended.     |
| `path`            | LineString  | The geographic route of the bank. Drawn on the map widget.       |
| `start_structure` | FK          | First end of the bank. Required at one of structure or location. |
| `end_structure`   | FK          | Second end of the bank.                                          |
| `start_face`      | choice      | Which face of the start structure (north/south/east/west/other). |
| `end_face`        | choice      | Which face of the end structure.                                 |
| `configuration`   | choice      | Layout shape, see table below. Leave blank if irregular.         |
| `total_conduits`  | int         | Designed capacity in slots. May be more than the actual count.   |
| `encasement_type` | choice      | Concrete, direct buried, bore, bridge attachment, tunnel.        |

The bank inherits the rest of `Pathway` (tenant, length, installation date,
comments).

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

## Bank Position On Conduits

Conduits inside a bank carry a `bank_position` like `A1` or `B3`:

- Row letter (`A`, `B`, ...) names the row, with `A` as the top.
- Column number (`1`, `2`, ...) names the column, with `1` on the left.
- The combination of `(conduit_bank, bank_position)` is unique. The
  database enforces this with a partial unique constraint when both fields
  are populated.

Position is a free-text field, so you can use any naming you like
(`L-1`, `R-2`, `slot-3a`). Stay consistent inside one organisation.

## Map Behaviour

A bank renders as a single LineString on the interactive map and on
exported QGIS layers. The conduits inside it do not appear as separate
features (`Conduit.map_visible` returns `False` when `conduit_bank` is
populated, and `Pathway.map_queryset` filters them out of the
`/api/plugins/pathways/geo/conduits/` and `/api/plugins/pathways/geo/pathways/`
GeoJSON endpoints).

To inspect the conduits inside a bank, open the bank detail page in NetBox
and use the conduits panel.

## Validation

Bank endpoints follow the same rules as any pathway:

- Exactly one start endpoint (structure or location).
- Exactly one end endpoint (structure or location).
- The `path` LineString must start and end within 1 metre of the
  configured structure geometries. The plugin snaps within tolerance and
  raises `ValidationError` outside it.

Junctions are not valid endpoints for a bank. Banks always run between two
structures or locations.
