# Circuit Geometry

A **Circuit Geometry** records a provider-described route for a NetBox
`circuits.Circuit`. The circuit itself remains a black box managed by
NetBox core; this model adds a LineString that says "the provider tells us
the circuit follows this physical path", suitable for display on the
infrastructure map.

## Why It Is Separate

NetBox's Circuits app describes services in business terms (provider,
type, status, terminations). It deliberately does not model the physical
path the carrier uses. Many operators still want to overlay carrier-
described routes on their plant map for awareness; that is what this
model is for.

The geometry is informational. It is not used for cable tracing, route
planning, or any pathway logic. Storing a route here does not create
`CableSegment` records or affect any other Pathways model.

## Fields

| Field                | Type            | Notes                                                                |
|----------------------|-----------------|----------------------------------------------------------------------|
| `circuit`            | OneToOne Circuit| The NetBox circuit this geometry belongs to.                         |
| `path`               | LineString      | The route, in your configured SRID. Always a LineString, never null. |
| `provider_reference` | string          | Provider's route ID, span ID, or document reference. Optional.       |
| `comments`           | text            | Free-form notes.                                                     |

## Display

The plugin exposes circuit geometries via the GeoJSON API at
`/api/plugins/pathways/geo/circuits/`. The serialised properties are:

| Property             | Source                          |
|----------------------|---------------------------------|
| `id`                 | `CircuitGeometry.id`            |
| `cid`                | `circuit.cid`                   |
| `provider`           | `circuit.provider.name`         |
| `circuit_type`       | `circuit.type.name`             |
| `status`             | `circuit.status`                |
| `provider_reference` | `CircuitGeometry.provider_reference` |

You can register this endpoint as a layer in QGIS, or rely on the
plugin's interactive map (where it can be enabled as a layer through
the layer toggle controls, when present).

## Workflow

1. Create the `circuits.Circuit` in NetBox core as usual (provider,
   type, terminations).
2. Navigate to **Plugins > Pathways > Circuit Geometries**.
3. Click **Add**, select the circuit, and draw the route on the map.
4. Optionally fill in `provider_reference` (for example, the provider's
   span/route ID printed on their fibre map) and `comments`.
5. Save.

## Updating Routes

Routes change when carriers re-engineer their network. Simply edit the
existing `CircuitGeometry` to update the path. Because the model is a
OneToOne to `Circuit`, there is at most one geometry per circuit; if you
need to record route history, use a custom field or comments rather than
multiple records.
