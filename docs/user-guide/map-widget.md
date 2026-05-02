# Map Widget On Forms

Every model with a geographic field is edited through a Leaflet map widget
embedded in the NetBox add/edit form. The widget is the same on every
form; this page covers what you can do with it and how it interacts with
the rest of the form.

## Where It Appears

| Model            | Geometry field        | Geometry type                 |
|------------------|-----------------------|-------------------------------|
| Structure        | `location`            | Point or Polygon              |
| ConduitBank      | `path`                | LineString                    |
| Conduit          | `path`                | LineString                    |
| AerialSpan       | `path`                | LineString                    |
| DirectBuried     | `path`                | LineString                    |
| Innerduct        | `path`                | LineString                    |
| SiteGeometry     | `geometry`            | Point or Polygon              |
| CircuitGeometry  | `path`                | LineString                    |

The widget configuration (tile layers, default centre, default zoom) is
read from `PLUGINS_CONFIG['netbox_pathways']`. See
[Configuration](../getting-started/configuration.md).

## Drawing Tools

The toolbar in the top-left of the widget shows tools appropriate to the
field's geometry type.

### Points

- **Marker tool** - click anywhere on the map to drop the point. The
  pin snaps to nearby Structure markers when within ~10 px on screen.
- **Drag** - move an existing marker by dragging.
- **Delete** - select the marker and press Delete or use the trash icon
  in the toolbar.

### LineStrings

- **Line tool** - click to start, click again to add vertices, double-
  click to finish.
- **Edit vertices** - click the line, then drag any vertex. Drag the
  midpoint diamonds to insert a new vertex.
- **Endpoint snapping** - the first and last vertex snap to the
  configured start/end Structure (or junction). If the endpoint sits
  more than 1 metre from the structure, the form rejects it on save.

### Polygons

- **Polygon tool** - click vertices in order, double-click to close.
- **Edit** - drag vertices or midpoints exactly as for lines. The shape
  closes automatically.

## Snapping And Tolerance

When you draw or edit a `path`, the plugin's `Pathway.clean()` method
checks each endpoint against the related Structure or Junction:

- For Point structures, the path endpoint must be within
  **1.0 metre** of the structure's point. If it is, the endpoint is
  snapped exactly onto the structure point. If not, you get a
  `ValidationError` on submit.
- For Polygon structures, the endpoint must be inside the polygon or
  within 1.0 metre of its boundary. Endpoints inside the polygon are
  snapped onto the boundary at the closest point. Outside that
  tolerance, submit fails.
- For Junctions, the endpoint must be within 1.0 metre of the
  junction's location (which is interpolated from the trunk
  conduit's geometry).

The 1 metre tolerance is in the units of your storage SRID. If you have
configured a degree-based SRID like `4326`, "1 metre" really means
"1 degree", which is far too lax. Use a metric projected SRID for
production deployments. See [SRID Selection](../getting-started/srid.md).

## Coordinate Reference Systems In The Widget

The widget uses Leaflet, which is hard-coded to WGS84. Behind the
scenes:

1. Stored geometry is read from the database in your storage SRID.
2. PostGIS transforms it to EPSG:4326 before serialising.
3. Leaflet displays it.
4. On save, the widget posts WGS84 GeoJSON; the plugin transforms back
   to the storage SRID before writing to the database.

You should never have to enter raw coordinates in your storage SRID
manually. If you do need to (for instance, copying a coordinate from
another system), the form accepts a WKT/GeoJSON paste in the underlying
text input that the widget wraps; check for it under the "Show advanced"
toggle on the widget when present.

## Multiple Base Layers

If `map_base_layers` is configured (typically Mapbox), the widget shows
a layer control in the top-right where you can switch between Street,
Light, Dark, and Satellite styles. The selection is per-tab, not
persisted.

## Detail-Page Mini Maps

Detail pages for the same models embed a smaller, read-only version of
the same map showing only that record. The mini map uses the same tile
configuration as the form widget.
