# Pathways

Pathways represent the physical routes that cables follow between structures and locations. Outdoor pathways have a LineString `geometry` defining their geographic route; indoor pathways (between two locations) have no geometry.

Every pathway is one record of a single `Pathway` model. Its **pathway type** decides which type-specific fields it has, what it may be placed inside, and whether the map draws it. All types share one list, one detail page and one add/edit form under `/plugins/pathways/pathways/`, and one REST endpoint at `/api/plugins/pathways/pathways/`.

## Pathway Types

| Type | Value | Description |
|------|-------|-------------|
| Conduit Bank | `conduit_bank` | An encased group of conduits sharing one route. See [Conduit Banks](conduit-banks.md). |
| Conduit | `conduit` | A pipe or duct that cables are pulled through. |
| Aerial Span | `aerial` | An overhead route hung between two supports, typically poles. |
| Direct Buried | `direct_buried` | A cable route buried directly in the ground, or a bundle of innerducts (microducts) buried without a conduit. |
| Innerduct | `innerduct` | A smaller duct inside another pathway, subdividing its capacity. Microducts are innerducts too, distinguished by `size`. |
| Cable Tray | `tray` | A tray carrying innerducts, usually inside a raceway. |
| Raceway | `raceway` | An enclosed channel holding conduits or trays. |
| Submarine | `submarine` | An underwater cable route. |

The type is chosen with the **Pathway Type** picker at the top of the add/edit form; changing it re-renders the form with that type's fields. An existing pathway may change type when its parent and children still satisfy the containment rule below. Fields that do not apply to the new type are cleared on save.

### Common fields

Every type has the label, status, endpoints, geometry, length, tenant, installer, dates, tags, custom fields and comments described on this page.

### Conduit

| Field | Description |
|-------|-------------|
| Material | PVC, HDPE, Steel, Concrete, Fiberglass |
| Inner Diameter | Inside diameter in millimeters |
| Outer Diameter | Outside diameter in millimeters |
| Depth | Burial depth in meters |
| Start/End Face | Which face of the start/end structure the conduit enters |
| Parent | Optional: the conduit bank or raceway this conduit is in |
| Position | Position within the parent (e.g., `A1`, `B2`); unique among the conduits of one parent |
| Start/End Junction | Optional junction endpoint (instead of a structure or location) |

### Conduit Bank

| Field | Description |
|-------|-------------|
| Start/End Face | Which face of the start/end structure the bank enters |
| Configuration | Layout such as `2x3`, or `custom` |
| Total Conduits | Designed capacity in slots |
| Height / Width | Number of duct rows / columns |
| Encasement Type | Concrete, direct buried, bore, bridge attachment, tunnel |

### Aerial Span

| Field | Description |
|-------|-------------|
| Aerial Type | Messenger, Self-support, Lashed, Wrapped, ADSS, OPGW |
| Start Attachment Height | Height of cable attachment at the start side, in meters. Nullable. |
| End Attachment Height | Height of cable attachment at the end side, in meters. Nullable. |
| Attachment Height (derived) | Read-only mean of the two sides; falls back to whichever side is populated, or `None` if both are unset. Exposed on the detail panel, list table, and REST API but not editable. |
| Sag | Maximum sag in meters |
| Messenger Size | Messenger wire specification |
| Wind Loading | Wind loading specification |
| Ice Loading | Ice loading specification |

#### Geometry of an aerial span

An aerial span hangs between two supports, so its geometry is not drawn
freely:

- **Both ends must be attached.** Each end needs a structure with geometry:
  the start/end structure, or the structure enclosing the start/end location
  (see [How pathway ends attach](attachment.md)). A span with a floating end
  is rejected, and so is a span whose two ends belong to the same structure.
- **It is always a straight line.** The geometry is exactly two vertices;
  intermediate vertices are dropped on save. The map editor hides the
  add-vertex handles and blocks vertex removal for aerial spans.
- **A pole pins its end.** On a point structure the end sits exactly on the
  structure, whatever coordinate was submitted.
- **A building offers a landing.** On a polygon structure (a building
  footprint, typically the structure linked from a Site Geometry) the end
  lands on the footprint's outline. Drag the end along the outline to choose
  where the span lands; the nearest outline point is kept. Without a drawn
  geometry the end lands on the wall facing the other support.

### Direct Buried

| Field | Description |
|-------|-------------|
| Burial Depth | Depth in meters |
| Warning Tape | Whether warning tape is installed |
| Tracer Wire | Whether tracer wire is installed |
| Armor Type | Cable armor specification |

### Innerduct

| Field | Description |
|-------|-------------|
| Parent | Required: the conduit, tray, direct buried pathway or innerduct it is inside |
| Size | Optional size (e.g., `1.25"`, `32mm`, `14/10mm` for a microduct) |
| Color | Color chosen from NetBox's color palette |
| Position | Position within the parent (not unique) |

Color is picked from NetBox's standard palette, the same widget used for rack
roles and cables, and renders as a swatch in pathway tables. CSV import also
accepts a color name (`Blue`) or a bare hex code (`2196f3`); `slate` and
`violet` from the telecom 12-color code map onto the nearest palette entries.

### Cable Tray, Raceway, Submarine

These types carry only the common fields. A raceway holds conduits and trays;
a tray holds innerducts; a submarine route holds nothing and is drawn on the
map.

## Hierarchy

A pathway may sit inside another pathway, its **parent**. The hierarchy is
stored as a PostgreSQL `ltree` path, so a pathway's ancestors (everything it
is inside) and descendants (everything inside it, at any depth) are each one
query. Moving a pathway under a new parent moves its whole subtree with it.

### Containment rule

| Parent | Allowed children |
|--------|------------------|
| Conduit Bank | Conduit |
| Raceway | Conduit, Cable Tray |
| Cable Tray | Innerduct |
| Conduit | Innerduct |
| Innerduct | Innerduct |
| Direct Buried | Innerduct |
| Aerial Span | nothing |
| Submarine | nothing |

- Conduits and cable trays may be top-level or have an allowed parent.
- Innerducts always have a parent.
- Every other type (conduit bank, raceway, aerial span, direct buried,
  submarine) is always top-level.

The rule is enforced by the model (`Pathway.clean()` and database check
constraints), so it applies equally to the UI, CSV import, the REST API and
netbox-branching merges. Changing the type of a pathway whose existing
children the new type may not contain is rejected; move or remove the
children first. The parent selector on the form only offers the allowed
parent types for the chosen type.

### Children on the detail page

A pathway's detail page lists its direct children, with an **Add** button that
opens the pathway form with the parent (and, when only one child type is
allowed, the type) preset. The parent's endpoints and shared type-specific
fields are pre-filled; lifecycle fields (installer, dates) are not copied for
innerducts, which are usually installed separately. The **Contents** tab lists
everything inside the pathway at any depth.

A child that leaves its start or end unset inherits it from its parent on
save. A child never needs its own geometry: it follows its parent's route, and
the geometry fallback walks up to the nearest ancestor that has one. A child
without a tenant shows the nearest ancestor's tenant marked with `*` in
tables.

### Deleting a pathway with children

`parent` is a protected relation. A pathway that still has children cannot be
deleted -- the UI shows NetBox's protected-object message listing them, and
the REST API returns `409 Conflict`. Reassign or delete the children first
(for example, unassign the conduits from a bank before deleting the bank).
Deleting a pathway with no children works as before.

## Permissions per pathway type

There is one `Pathway` object type, so NetBox object permissions cover every
pathway type at once. To limit a permission to some types, add a constraint on
`pathway_type`:

```json
{"pathway_type": "conduit"}
```

```json
{"pathway_type__in": ["conduit", "innerduct"]}
```

A permission with the first constraint lets its users view (or change, per its
actions) conduits only. See NetBox's
[permissions documentation](https://netboxlabs.com/docs/netbox/administration/permissions/)
for the constraint syntax.

## Endpoints

Every pathway has a start endpoint and an end endpoint. These can be:

- **Structure** -- An outdoor structure (pole, manhole, etc.)
- **Location** -- An indoor NetBox location (room, floor)
- **Junction** -- A conduit junction (conduits only)

You can mix endpoint types. For example, a conduit starting at a manhole (structure) and ending at an equipment room (location) models a building entrance path.

### Indoor pathways

When both endpoints are locations, the pathway is indoor and the geometry is optional -- NetBox locations carry no coordinates, so there is nothing to draw. Simply pick the two locations and save; the pathway is created without geometry and does not appear on the interactive map or in the GeoJSON API layers. A geometry is still required whenever either endpoint is geographic (a structure or a junction), unless the pathway has a parent.

## Creating a Pathway

1. Navigate to **Plugins > Pathways > Pathways** and click **Add**, or use the
   **Add** button next to a pathway type's quick link in the menu (for example
   **Conduits**), which presets the type
2. Choose the **Pathway Type**; the form shows that type's fields
3. Set the label, endpoints, parent (where the type allows one) and type-specific fields
4. Draw the geometry on the map widget or enter it manually (not needed for a pathway with a parent)
5. Save

The per-type menu links open the pathway list filtered with
`?pathway_type=<type>`.

!!! tip
    The map widget snaps to nearby structures when drawing a geometry. Start and end your line near your selected structures for accurate geometry.

## Pathway on the Map

The interactive map draws only **containers**: conduit banks, top-level
conduits, aerial spans, direct buried pathways and submarine routes, and only
when they have no parent. Innerducts, cable trays, raceways and any pathway
with a parent are never drawn on their own; the outermost drawn pathway that
contains them stands for them. See
[Interactive Map](interactive-map.md#what-the-map-draws) for the styles and
for how the Map button, `?select=` and map search resolve a child.

Clicking a pathway line opens the sidebar with details including endpoints, length, type-specific attributes, and routed cables.

## Length: drawn vs as-built

Every pathway carries two length values:

| Field | Source | Use |
|-------|--------|-----|
| Length (m, as-built) | User-entered `length` field on the pathway record | Field-measured / as-built length: includes slack, riser drops, sag, and any vertical component the LineString does not capture. |
| Geo length (m, drawn) | Read-only `geo_length`, computed by PostGIS `ST_Length` on the `geometry` LineString | The horizontal distance of the drawn geometry. Always reflects the current shape on the map. |

The two values are intentionally separate -- they usually disagree, and that disagreement is information (slack, vertical drops, recently re-drawn geometry that has not been re-measured in the field, etc.).

`geo_length` is exposed:

- on the detail panel next to `Length (m, as-built)`,
- as a sortable "Geo length (m)" column on each pathway list (off by default; toggle from the "Configure" menu),
- on the REST API and GeoJSON endpoints (read-only),
- as range filter parameters `?geo_length__gte=...` and `?geo_length__lte=...` on every Pathway list / API endpoint.

!!! note
    `geo_length` returns metres. The plugin's `PLUGINS_CONFIG['netbox_pathways']['srid']` must be a projected, metre-based CRS (e.g. an EPSG code for a local UTM zone or NAD83 Lambert Conformal Conic). The same requirement already underpins every other distance / area output in the plugin, so most installs need no extra configuration.

## Lifecycle

Every pathway carries the following lifecycle fields, in addition to the type-specific fields above:

| Field | Description |
|-------|-------------|
| Status | Lifecycle state: `Planned`, `Active` (default), `Under Construction`, `Decommissioning`, `Retired`, or `Abandoned in place` -- the same states as structures. The route planner skips `Retired` and `Decommissioning` pathways unless "Include inactive/retired" is checked. |
| Installation Date | When the pathway was physically installed |
| Commissioned Date | When the pathway was commissioned / accepted (often after the install date for outside-plant work) |
| Tenant | Tenant served by / customer assigned to this pathway |
| Installed By | Tenant entry for the contractor or workforce that physically installed the pathway (distinct from `Tenant`) |

## Filtering

Pathway lists support filtering by:

- **Status** -- Filter by lifecycle state
- **Pathway Type** -- Conduit, Aerial, Direct Buried, etc. (`?pathway_type=conduit`)
- **Parent** -- Direct children of a pathway (`?parent_id=<id>`)
- **Ancestor / Descendant** -- `?ancestor_id=<id>` keeps everything inside a pathway at any depth; `?descendant_id=<id>` keeps every pathway that contains it
- **Start/End Structure** -- Filter by connected structures
- **Site** -- Filter by associated site
- **Type-specific fields** -- Material, aerial type, encasement and the other type fields, grouped per type on the filter form
- **Tenant** -- Filter by owning tenant (served customer)
- **Installed By** -- Filter by installer/contractor tenant
- **Installation Date** / **Commissioned Date** -- Filter by date
- **Has Path** -- Filter pathways with/without geometry
- **Geo length range** -- `?geo_length__gte=<m>` and `?geo_length__lte=<m>` filter pathways by their drawn length. Filtering runs as a PostGIS `ST_Length(geometry)` predicate, so it scales with database indexes rather than Python iteration.

## Intermediate Locations

Pathways can pass through intermediate locations (sites or rooms) along their route. Use **Pathway Locations** to record these waypoints with sequence numbers for ordering. This is useful for documenting that a conduit passes through multiple manholes along its route.

## Cloning

Every pathway detail view has a Clone button. Cloning pre-fills the
create form with the source object's type, parent, status, endpoints,
installer, dates, and type-specific attributes (faces for conduits, span
attributes for aerial spans, burial attributes for direct buried pathways,
size and color for innerducts). The geometry, label, and position within
the parent are never copied, so you can document parallel runs quickly and
then draw each one.

## Keeping pathway ends attached to structures

Pathway ends follow the structures they are attached to. When a structure's
geometry is edited -- in the UI, through the REST API, by CSV import or by
bulk edit -- every pathway end belonging to it (directly, or through a location
it encloses -- see [How pathway ends attach](attachment.md)) moves with it,
in the same transaction:

- Conduits, direct buried pathways and other pathways keep their interior
  vertices; only the end vertex moves.
- Aerial spans are rebuilt as the straight line between their supports.
- An end on a moved or reshaped building keeps its relative position on the
  outline, so a landing on the east wall stays on the east wall.
- Conduits branching off a moved conduit at a junction follow the junction's
  new position.

Each rewritten pathway gets its own change-log entry.

Writes that bypass a structure's save -- queryset `update()`,
`bulk_update`, raw SQL, a restored database dump -- leave pathway ends
behind. The `reanchor_pathways` management command finds and repairs them:

```
python manage.py reanchor_pathways                       # report only
python manage.py reanchor_pathways --structure 17 23     # pathways on these structures
python manage.py reanchor_pathways --type aerial --apply # repair aerial spans
```

It reports every pathway end farther than the endpoint tolerance (1.0 SRID
unit) from its structure or junction, and every aerial span that is bent
(more than two vertices) or detached. `--apply` repairs everything found in
one transaction: ends land on their structure (the nearest outline point for
a building, since the geometry before the bulk write is unknown), aerial
spans are straightened, and junction branches follow. Detached aerial spans
are reported but left alone -- there is no structure to land them on; attach
them in the UI. As with `split_pathway`, `--user <username>` runs the repair
inside NetBox's event pipeline so it is recorded in the change log.

## Splitting an imported pathway at structures

Geometry imported from KMZ files or other OSP tools often arrives as one
long polyline that physically passes many structures (a pole line, for
example) but is stored as a single pathway. In the pathways data model a
span is the hop between two structures, so the mid-span structures are not
connected to the pathway at all: nothing can branch or be routed at them,
and per-hop attributes cannot be recorded.

The `split_pathway` management command replaces such a pathway with
consecutive per-hop pathways of the same type:

```
python manage.py split_pathway 42                     # preview candidates
python manage.py split_pathway 42 --exclude 17 --apply
```

The default run is a dry-run preview: it detects structures within
`--tolerance` (SRID units, default 1.0) of the pathway's line, excluding
its endpoints, and prints them ordered by chainage together with each
structure's offset from the line and the resulting hop layout. Nothing is
written until you re-run with `--apply`.

- `--exclude ID ...` drops false positives from the detected candidates
  (a parallel pole line caught by the tolerance, for example).
- `--structures ID ...` bypasses detection and splits at exactly the given
  structures.

On apply, in one transaction:

- The pathway is replaced by one child per hop, with vertices preserved and
  the cut vertices snapped onto the structure points. Shared attributes,
  tags, and custom fields are copied; per-side attributes (faces,
  attachment heights) stay on the first and last child; labels get an
  `(i/total)` suffix.
- Everything inside the pathway, at any depth (a bank's conduits and
  their innerducts, innerducts in a direct buried pathway), is cascaded
  into per-hop copies attached to the corresponding hop.
- Cable segments routed through the pathway are replaced by per-hop
  segments in path order, preserving sequence order and lashing.
- The original pathway is deleted.

The command refuses indoor pathways (no geometry) and pathways with a
parent (split the container instead), and conduits with
junctions (their positions along the trunk would be invalidated). Planned
routes referencing the pathway are reported so they can be re-planned;
waypoints cannot be repositioned and are deleted with the original.

By default `split_pathway` operates outside NetBox's request pipeline:
the deletion and creations do not produce change-log entries, webhooks,
or event-rule triggers, and the dry-run preview is the review step. Pass
`--user <username>` to run the apply inside the event pipeline instead --
the change log then records the split attributed to that user (grouped
under a single request id), and webhooks and event rules fire as they
would for a UI edit.
