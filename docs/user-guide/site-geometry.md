# Site Geometry

A **Site Geometry** record links a NetBox `dcim.Site` to the Pathways
geospatial system. It is a thin model with two responsibilities:

1. Hold an explicit boundary or footprint geometry for a Site that is not
   itself one of your Structures.
2. Provide a fallback geometry when a Site is "the same physical thing"
   as a Structure (for example, a single-building site that you also
   model as a Building Entrance Structure).

## Why It Exists

NetBox's `dcim.Site` does not have a geometry field. The Pathways plugin
needs a way to anchor data on a Site for two cases:

- The map registry. Other plugins can register layers whose geometry is
  resolved through `dcim.Site` (see the
  [Map Layer Registry](../developer/map-layer-registry.md)). The lookup
  path is `pathways_geometry__geometry`, which only works when a
  `SiteGeometry` row exists for that site.
- Drawing site outlines or campus footprints on the map without forcing
  every site to be modelled as a Structure.

## Fields

| Field      | Type                | Notes                                                                                  |
|------------|---------------------|----------------------------------------------------------------------------------------|
| `site`     | OneToOne `dcim.Site`| Required. Each site has at most one geometry record.                                   |
| `structure`| OneToOne Structure  | Optional. If set, the site "is" this structure.                                        |
| `geometry` | Point or Polygon    | Optional. Explicit geometry. Auto-populated from `structure.location` if blank on save.|
| `comments` | text                |                                                                                        |

## Geometry Resolution

The `effective_geometry` property returns the right geometry to use:

1. If `geometry` is set, use it.
2. Otherwise, if `structure` is set and the structure has a `location`,
   use `structure.location`.
3. Otherwise, return `None`.

`SiteGeometry.save()` automatically copies the structure's geometry into
the explicit `geometry` field if the field is blank when a structure is
attached. After save, the explicit field is populated, and edits to the
structure no longer feed back automatically. Re-link the structure or
clear the `geometry` field if you want to refresh the copy.

## When To Create A Site Geometry

| Situation                                                              | Create one? |
|------------------------------------------------------------------------|-------------|
| You want to draw a site polygon on the Pathways map.                   | Yes.        |
| Another plugin's models reference `dcim.Site` and need map placement.  | Yes.        |
| The site is identical to a single Structure you already created.       | Optional. Helpful for plugins doing reverse lookups; otherwise the Structure alone is enough. |
| You only ever route through Structures inside the site, not the site itself. | No.   |

## Map Display

Site polygons render with a 20% fill opacity and the layer's stroke
colour. They are not toggled on by default and must be wired through a
registered map layer (typically by your own plugin) to appear on the
map.

The plugin's first-party map does not show site geometries directly; the
feature exists primarily as the geometry source for cross-plugin layers.

## Forms

Create or edit a `SiteGeometry` at
`/plugins/pathways/site-geometries/`. The form uses the standard map
widget, so you can click the map to drop a point or use the polygon tool
to draw a footprint.
