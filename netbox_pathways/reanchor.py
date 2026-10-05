"""Keep pathway ends attached to the structures they hang from.

When a structure's geometry changes, every pathway end anchored to it moves
with it: the end vertex only, so a conduit keeps its surveyed bends, while an
aerial span is rebuilt as the straight line it always is. Conduits that branch
off a moved conduit at a junction follow the junction's new position.

Each pathway change goes through snapshot() + save() so NetBox records it in
the changelog like any other edit.
"""

from django.contrib.gis.geos import LineString, Point
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .landing import relocate

SIDES = ("start", "end")


def end_point(pathway, side):
    """The first or last vertex of the pathway's path as a Point."""
    x, y = pathway.path.coords[0 if side == "start" else -1][:2]
    return Point(x, y, srid=pathway.path.srid)


def set_end(pathway, side, point):
    """Replace the first or last vertex of the pathway's path."""
    coords = list(pathway.path.coords)
    coords[0 if side == "start" else -1] = (point.x, point.y)
    pathway.path = LineString(coords, srid=pathway.path.srid)


def straighten_if_aerial(pathway):
    """Rebuild an aerial span as its straight line; leave other types alone.

    A legacy span with a detached end cannot be straightened; its anchored end
    has already moved, which is the best that can be done for it.
    """
    from .models import AerialSpan

    if isinstance(pathway, AerialSpan):
        try:
            pathway.straighten()
        except ValidationError:
            pass


def anchored_sides(pathway, structure):
    """Sides of the pathway whose anchor structure is `structure`."""
    sides = []
    for side in SIDES:
        anchor = pathway.anchor_structure(side)
        if anchor is not None and anchor.pk == structure.pk:
            sides.append(side)
    return sides


def pathways_anchored_to(structure):
    """Pathways with a path whose start or end resolves to `structure`."""
    from .models import Pathway

    query = Q(start_structure=structure) | Q(end_structure=structure)
    if structure.location_id:
        query |= Q(start_structure__isnull=True, start_location_id=structure.location_id)
        query |= Q(end_structure__isnull=True, end_location_id=structure.location_id)
    return Pathway.objects.filter(query, path__isnull=False)


def reanchor_structure(structure, old_geom):
    """Move every pathway end anchored to `structure` from `old_geom` to its geometry.

    Returns the pathways that were rewritten, junction branches included.
    """
    moved = []
    with transaction.atomic():
        for row in pathways_anchored_to(structure):
            pathway = row.as_concrete()
            pathway.snapshot()
            for side in anchored_sides(pathway, structure):
                set_end(pathway, side, relocate(old_geom, structure.geometry, end_point(pathway, side)))
            straighten_if_aerial(pathway)
            pathway.save()
            moved.append(pathway)
        moved.extend(_cascade_junctions(moved))
    return moved


def _cascade_junctions(moved):
    """Drag branch conduit ends to the new position of their junction.

    A branch that moves may itself be a trunk for further junctions, so the
    walk continues until no junction is left to visit.
    """
    from .models import Conduit, ConduitJunction

    cascaded = []
    visited = set()
    queue = [pathway for pathway in moved if isinstance(pathway, Conduit)]
    while queue:
        trunk = queue.pop()
        for junction in ConduitJunction.objects.filter(trunk_conduit=trunk):
            if junction.pk in visited:
                continue
            visited.add(junction.pk)
            junction.trunk_conduit = trunk
            target = junction.derived_geometry
            branches = Conduit.objects.filter(Q(start_junction=junction) | Q(end_junction=junction), path__isnull=False)
            for branch in branches:
                branch.snapshot()
                for side in SIDES:
                    if getattr(branch, f"{side}_junction_id") == junction.pk:
                        set_end(branch, side, target)
                branch.save()
                cascaded.append(branch)
                queue.append(branch)
    return cascaded
