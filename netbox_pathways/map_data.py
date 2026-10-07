"""Inline map data shared by the plugin's detail maps.

The {points, lines, polygons} payload rendered by inc/geo_map_panel.html and
drawn by detail-map.ts (initGeoMap). Used by the map panels injected into
NetBox pages (template_content.py) and the cable Map tab (route_map.py).
"""

from .geo import linestring_to_coords, point_to_latlon, to_leaflet

PATHWAY_COLORS = {
    "conduit": "brown",
    "aerial": "blue",
    "direct_buried": "gray",
    "innerduct": "orange",
    "microduct": "purple",
    "tray": "green",
    "raceway": "cyan",
    "submarine": "navy",
}

STRUCTURE_COLORS = {
    "pole": "green",
    "manhole": "blue",
    "handhole": "cyan",
    "cabinet": "orange",
    "vault": "purple",
    "pedestal": "yellow",
    "building_entrance": "red",
    "tower": "darkred",
    "roof": "gray",
    "equipment_room": "teal",
    "telecom_closet": "indigo",
    "riser_room": "pink",
}


def pathway_line(pathway):
    """Build a line dict from a Pathway instance."""
    if not pathway.path:
        return None
    return {
        "coords": linestring_to_coords(pathway.path),
        "name": str(pathway),
        "color": PATHWAY_COLORS.get(pathway.pathway_type, "gray"),
        "url": pathway.get_absolute_url(),
    }


def structure_point(structure, color=None, muted=False):
    """Build a point dict from a Structure instance.

    `muted` marks a structure shown only as context for something else (the far
    end of a pathway leaving the page's subject); the map draws those faded.
    The key is omitted when false so the common case costs nothing in a payload
    that can carry 500 points.
    """
    # Structure.geometry is required, so a saved structure always has a centroid.
    latlon = point_to_latlon(structure.centroid)
    point = {
        "lat": latlon[0],
        "lon": latlon[1],
        "name": structure.name,
        "structure_type": structure.get_structure_type_display(),
        "color": color or STRUCTURE_COLORS.get(structure.structure_type, "gray"),
        "url": structure.get_absolute_url(),
    }
    if muted:
        point["muted"] = True
    return point


def footprint_ring(structure):
    """Return the exterior ring of a Structure's footprint, or None.

    A Structure is drawn as either a marker or a footprint -- the geometry
    widget offers drawMarker and drawPolygon only -- so anything that is not a
    polygon is a point as far as the map is concerned.
    """
    geom = structure.geometry
    if geom is None or geom.geom_type != "Polygon":
        return None
    return [[p[0], p[1]] for p in to_leaflet(geom).exterior_ring.coords]


def add_structure(data, structure, color=None, muted=False, name=None):
    """Append a Structure to `data` as a footprint outline or a point marker.

    `name` overrides the label shown in its popup (the structure's name).

    Footprints keep their centroid alongside the ring so the client can swap in
    a single icon below the footprint zoom, where an outline is sub-pixel.
    """
    shape = structure_point(structure, color=color, muted=muted)
    if name is not None:
        shape["name"] = name
    ring = footprint_ring(structure)
    if ring is None:
        data["points"].append(shape)
    else:
        shape["coords"] = ring
        data["polygons"].append(shape)
