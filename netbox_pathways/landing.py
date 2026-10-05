"""Where a pathway end lands on the structure it is attached to.

A point structure (pole, handhole) pins the end exactly. An area structure
(building footprint) offers its whole boundary: the end may land anywhere on
it, so these helpers pick the boundary point a caller asks for -- the one
nearest a hint, or the one at the same relative position after the
structure moved.

Pure GEOS: nothing here touches the database.
"""


def is_area(geom):
    return geom.geom_type != "Point"


def reference_point(geom):
    """The point that stands for a structure when no landing is known yet."""
    return geom.centroid if is_area(geom) else geom


def landing_on(geom, near):
    """The point of `geom` an end near `near` lands on.

    For an area that is the closest point of its boundary, whether `near`
    lies inside or outside the footprint.
    """
    if not is_area(geom):
        return geom
    boundary = geom.boundary
    return boundary.interpolate(boundary.project(near))


def relocate(old_geom, new_geom, pt):
    """Where an end that sat at `pt` on `old_geom` goes once it is `new_geom`.

    Area to area keeps the end at the same fraction of the boundary, so a
    moved building keeps the landing on the same wall instead of snapping to
    whichever wall now happens to be nearest. Without a comparable old area
    (unknown, or a point that became an area) the nearest landing is used.
    """
    if not is_area(new_geom):
        return new_geom
    if old_geom is None or not is_area(old_geom):
        return landing_on(new_geom, pt)
    fraction = old_geom.boundary.project_normalized(pt)
    return new_geom.boundary.interpolate_normalized(fraction)
