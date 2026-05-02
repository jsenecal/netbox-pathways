# Route Planner

The Route Planner finds candidate paths through your pathway network
between a start endpoint (structure or location) and an end endpoint. It
operates on the same graph the cable trace uses: structures, locations,
and junctions are nodes; pathways and bank-to-conduit relationships are
edges.

The output is one or more **Planned Routes**, ordered lists of pathway
PKs that you can review, save, edit, and eventually apply to a real
NetBox `dcim.Cable`.

## Opening The Planner

Navigate to **Plugins > Pathways > Route Planner** or visit
`/plugins/pathways/route-planner/`.

The planner page shows a map and a sidebar. Pick endpoints either by
clicking features on the map or by selecting from the dropdowns.

## Endpoints

| Endpoint side | Allowed types                         |
|---------------|---------------------------------------|
| Start         | Structure or `dcim.Location`          |
| End           | Structure or `dcim.Location`          |

A route may start at a Structure and end at a Location (or vice versa);
this is how the planner finds cross-domain paths between an outdoor
structure and an indoor wiring closet.

## Constraints

Constraints narrow the search. They are interpreted by
`/plugins/pathways/route-planner/constraint/` and recorded on the saved
plan as a JSON snapshot.

| Constraint             | Effect                                                   |
|------------------------|----------------------------------------------------------|
| Required pathway       | Force the route to traverse a specific pathway.          |
| Excluded pathway       | Refuse to use a specific pathway.                        |
| Tenant filter          | Only use pathways owned by a tenant.                     |
| Pathway type filter    | Restrict to certain types (e.g. only conduits).          |

The current run's constraint set is shown in the sidebar; you can
remove a constraint with the X button next to it.

## Running A Search

1. Select start and end endpoints.
2. Add any constraints.
3. Click **Find Routes**.
4. The planner returns up to several candidate routes. Each route lists
   its pathways in order, total length, hop count, and any pathway types
   that conflict with your constraints.
5. Pick the route you want and click **Save**. This creates a
   `PlannedRoute` record with status `draft`.

## Planned Routes

A Planned Route is a saved route that has not yet been bound to a real
`dcim.Cable`. Fields:

| Field             | Type             | Notes                                                                |
|-------------------|------------------|----------------------------------------------------------------------|
| `name`            | string           | Required. Used as the page title.                                    |
| `status`          | choice           | `draft`, `approved`, `assigned`, `split`, `archived`.                |
| `start_structure` | FK Structure     | Either start_structure or start_location must be set, never both.    |
| `start_location`  | FK Location      |                                                                      |
| `end_structure`   | FK Structure     | Either end_structure or end_location must be set, never both.        |
| `end_location`    | FK Location      |                                                                      |
| `pathway_ids`     | JSON list of int | Ordered list of pathway PKs defining the route.                      |
| `constraints`     | JSON dict        | Snapshot of the constraints used to generate the route.              |
| `tenant`          | FK Tenant        | Optional owning tenant.                                              |
| `cable`           | FK Cable         | Set when the route is applied to a real cable.                       |
| `parent`          | FK PlannedRoute  | If non-null, this route was split from another route.                |

### Status Transitions

| From       | To           | When                                                |
|------------|--------------|-----------------------------------------------------|
| `draft`    | `approved`   | Manual review.                                      |
| `approved` | `assigned`   | Route applied to a cable.                           |
| `approved` | `split`      | Route split into child routes for partial install.  |
| any        | `archived`   | Route is no longer relevant but you want history.   |

The transitions are not enforced by code; the choices help operators
filter and report.

## Splitting And Reverting

A route can be split into smaller child routes that share the same
endpoints but cover different segments. Splitting is useful when one
plan covers the full path but the build will happen in phases.

- `POST /plugins/pathways/planned-routes/<pk>/split/` opens the split
  form. Children inherit `parent = <pk>` and the parent transitions to
  `split`.
- `POST /plugins/pathways/planned-routes/<pk>/revert/` deletes the
  children and restores the parent to its previous status.

## Applying A Plan To A Cable

When the cable exists in NetBox and is ready for real routing data:

1. Open the Planned Route detail page.
2. Click **Apply**.
3. Select the target `dcim.Cable`.
4. The plugin creates one `CableSegment` per pathway in
   `pathway_ids`, in order, and sets the route's status to `assigned`.

The cable must already have both A and B terminations recorded in
NetBox before applying; `CableSegment.clean()` raises a validation error
otherwise.

## Validation Helper

`PlannedRoute.validate_route()` returns the list of pathway PKs that no
longer exist in the database. Routes with missing pathways will be
rejected at apply time. Run this method (via the Django shell, the API,
or the management UI) before approving a route that has been sitting
around for a while.
