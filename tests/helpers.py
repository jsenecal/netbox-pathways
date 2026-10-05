"""Geometry fixtures shared by the landing, aerial span and reanchoring tests.

Coordinates are in the plugin SRID, so 1 unit is 1 metre on a projected SRID.
"""

from django.contrib.gis.geos import LineString, Point, Polygon

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, Conduit, Structure

SRID = get_srid()


def square(x0, y0, size=10):
    """A square footprint with its south-west corner at (x0, y0)."""
    ring = ((x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0))
    return Polygon(ring, srid=SRID)


def make_pole(name, x, y):
    """A saved point structure."""
    return Structure.objects.create(name=name, geometry=Point(x, y, srid=SRID))


def make_building(name, x0, y0, size=10):
    """A saved polygon structure: a square footprint."""
    return Structure.objects.create(name=name, geometry=square(x0, y0, size))


def make_conduit(path, **kwargs):
    """A saved conduit along `path` (a list of (x, y) vertices)."""
    instance = Conduit(path=LineString(path, srid=SRID), **kwargs)
    instance.save()
    return instance


def make_aerial_span(start, end):
    """A saved aerial span between two structures, path derived by clean()."""
    span = AerialSpan(start_structure=start, end_structure=end)
    span.full_clean()
    span.save()
    return span


def coords(pathway, refresh=False):
    """The pathway's path vertices, rounded; reloaded from the database when `refresh`."""
    if refresh:
        pathway.refresh_from_db()
    return [(round(x, 6), round(y, 6)) for x, y in pathway.path.coords]
