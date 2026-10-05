# How Pathway Ends Attach to Structures

A pathway end can name a **structure**, a NetBox **location**, or (conduits
only) a **junction**. Many features need to know which *structure* an end
belongs to: snapping the drawn line, hanging aerial spans, moving pathways
when a structure moves, and listing a structure's pathways. This page
describes the rules the plugin follows. They are applied automatically; you
do not set them anywhere.

## Two links between structures and NetBox

A structure can stand for something NetBox already knows about:

| Link | Set on | Meaning |
|------|--------|---------|
| **Structure is a location** | the structure's *Location* field | "This vault *is* the location *Vault Row A*." |
| **Structure is a site** | the site's [Site Geometry](site-geometry.md) *Structure* field | "This building *is* the site *Building A*." |

A structure's *Site* field is different: it only says the structure **sits
in** a site. It never makes the structure stand for the site.

## The rule: nearest enclosing structure

An end that names a structure belongs to that structure.

An end that names a location belongs to the **nearest structure enclosing
that location**:

1. the structure that *is* the location, if any;
2. otherwise the structure that *is* the nearest parent location;
3. otherwise the structure that *is* the location's site;
4. otherwise none -- the end is unattached.

### Example

```
Site "Building A"          is building B (a footprint polygon)
 |- Floor 1
 |   '- Room 101
 '- Vault Row A            is vault V1 (a point)
     '- Shelf 3
```

| End names | Belongs to | Why |
|-----------|------------|-----|
| Vault Row A | V1 | V1 is Vault Row A |
| Shelf 3 | V1 | nearest parent location with a structure |
| Room 101 | B | no structure on Room 101 or Floor 1; B is the site |
| a location in a site without a structure | nothing | unattached |

## One endpoint kind per side

Each side of a pathway names exactly one of: a structure, a location, or a
junction (conduits). Naming both a structure and a location on the same side
is rejected, because it would be ambiguous where the pathway ends.

## What uses the rule

**Geometry.**

- The drawn line's end is snapped onto the structure: onto a point
  structure exactly, onto the outline of a footprint. An end inside a
  footprint counts as attached and is moved onto the outline.
- [Aerial spans](pathways.md#geometry-of-an-aerial-span) must attach to two
  *different* structures. An aerial span to *Room 101* hangs from building
  B and lands on its outline.
- When a structure moves, every pathway end belonging to it moves too --
  including ends that name a location inside it
  (see [Keeping pathway ends attached](pathways.md#keeping-pathway-ends-attached-to-structures)).

**Membership.** A structure's pathways are the pathways with an end
belonging to it:

- the Conduit Banks, Conduits, Aerial Spans and Direct Buried tabs and their
  counts on the structure page;
- the *Connected structures* panel (structures at the far end of those
  pathways);
- the REST API: `no_pathways` on structures, the `has_pathways` and
  `occupied` structure filters, and the `structure_id` filter on pathways;
- split candidates for `split_pathway` (a pathway's own structures are never
  split points).

The REST and GeoJSON APIs expose the result on each pathway as read-only
`start_anchor` / `end_anchor`. The plain field filters (`start_structure_id`,
`end_structure_id`) keep matching the field value only.

## What does not use the rule: route planning

The route planner and the Route tab picker treat *Room 101* and building B as
**different places**, so routing inside a building still follows the trays
and conduits between rooms instead of jumping through the building. Only the
fields a pathway actually names connect it in the route graph.

## Keeping the answer current

The structure each end belongs to is stored on the pathway and recomputed
when:

- the pathway is saved;
- a structure's *Location* is set, changed or cleared;
- a structure is deleted (its ends fall back up the rule);
- a site's Site Geometry structure is linked or unlinked;
- a location moves to another parent or site.

Writes that bypass NetBox's normal save -- queryset `update()`, raw SQL, a
restored database dump -- can leave the stored answer stale.
`python manage.py reanchor_pathways` reports stale answers, ends that no
longer sit on their structure, and sides naming two endpoint kinds;
`--apply` repairs everything except the sides naming two kinds, which need a
person to choose.
