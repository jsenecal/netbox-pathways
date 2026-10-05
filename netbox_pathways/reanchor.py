"""Keep pathway ends attached to the structures they hang from.

When a structure's geometry changes, every pathway end anchored to it moves
with it: the end vertex only, so a conduit keeps its surveyed bends, while an
aerial span is rebuilt as the straight line it always is. Conduits that branch
off a moved conduit at a junction follow the junction's new position.

Writes that bypass Structure.save() (queryset update(), bulk_update, raw SQL)
leave ends behind; find_drift() and repair() serve the reanchor_pathways
command that puts them back.

Each pathway change goes through snapshot() + save() so NetBox records it in
the changelog like any other edit.
"""

from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from .landing import attaches, end_point, landing_on, relocate, with_end
from .registry import LOCATION_IDENTITY_ACCESSOR

SIDES = ("start", "end")


def _rewrite(pathway, placements):
    """Move ends to `placements` ({side: Point}), straighten aerial spans, save.

    A legacy aerial span with a detached end cannot be straightened; its
    anchored end still moves, which is the best that can be done for it.
    """
    from .models import AerialSpan

    pathway.snapshot()
    for side, point in placements.items():
        pathway.path = with_end(pathway.path, side, point)
    if isinstance(pathway, AerialSpan):
        try:
            pathway.straighten()
        except ValidationError:
            pass
    pathway.save()


def pathways_anchored_to(structure):
    """Pathways with a path whose start or end resolves to `structure`."""
    from .models import Pathway

    query = Q(start_structure=structure) | Q(end_structure=structure)
    if structure.location_id:
        query |= Q(start_structure__isnull=True, start_location_id=structure.location_id)
        query |= Q(end_structure__isnull=True, end_location_id=structure.location_id)
    return Pathway.objects.filter(query, path__isnull=False)


def concrete_pathways(pathways):
    """Pathways with a path, as subclass instances, with their anchors preloaded.

    One query per pathway type instead of several per pathway: the endpoint
    structures, location identity structures and junction trunks that
    anchor resolution walks are fetched with select_related.
    """
    from .models import PATHWAY_TYPE_MODELS, Conduit, Pathway

    pks = pathways.filter(path__isnull=False).values("pk")
    anchors = (
        "start_structure",
        "end_structure",
        f"start_location__{LOCATION_IDENTITY_ACCESSOR}",
        f"end_location__{LOCATION_IDENTITY_ACCESSOR}",
    )
    junctions = ("start_junction__trunk_conduit", "end_junction__trunk_conduit")
    querysets = [
        model.objects.filter(pk__in=pks).select_related(*anchors, *(junctions if model is Conduit else ()))
        for model in PATHWAY_TYPE_MODELS.values()
    ]
    querysets.append(
        Pathway.objects.filter(pk__in=pks).exclude(pathway_type__in=PATHWAY_TYPE_MODELS).select_related(*anchors)
    )
    return sorted((pathway for queryset in querysets for pathway in queryset), key=lambda pathway: pathway.pk)


def reanchor_structure(structure, old_geom):
    """Move every pathway end anchored to `structure` from `old_geom` to its geometry."""
    with transaction.atomic():
        moved = []
        for pathway in concrete_pathways(pathways_anchored_to(structure)):
            placements = {
                side: relocate(old_geom, structure.geometry, end_point(pathway.path, side))
                for side in SIDES
                if getattr(pathway.anchor_structure(side), "pk", None) == structure.pk
            }
            _rewrite(pathway, placements)
            moved.append(pathway)
        _cascade_junctions(moved)


def _cascade_junctions(moved):
    """Drag branch conduit ends to the new position of their junction.

    A branch that moves may itself be a trunk for further junctions, so the
    walk continues until no junction is left to visit.
    """
    from .models import Conduit, ConduitJunction

    visited = set()
    queue = [pathway for pathway in moved if isinstance(pathway, Conduit)]
    while queue:
        trunk = queue.pop()
        for junction in ConduitJunction.objects.filter(trunk_conduit=trunk).exclude(pk__in=visited):
            visited.add(junction.pk)
            junction.trunk_conduit = trunk
            target = junction.derived_geometry
            branches = Conduit.objects.filter(Q(start_junction=junction) | Q(end_junction=junction), path__isnull=False)
            for branch in branches:
                _rewrite(
                    branch, {side: target for side in SIDES if getattr(branch, f"{side}_junction_id") == junction.pk}
                )
                queue.append(branch)


# --- Repair: ends left behind by writes that bypassed Structure.save() -------


@dataclass
class Drift:
    """A pathway whose ends no longer sit on what they are attached to."""

    pathway: object
    problems: list = field(default_factory=list)
    # A detached aerial span has no structure to land on: report, never rewrite.
    repairable: bool = True


def find_drift(pathways):
    """Drift for each pathway in `pathways` that has a problem, in order."""
    from .models import ENDPOINT_TOLERANCE, AerialSpan

    found = []
    for pathway in concrete_pathways(pathways):
        is_aerial = isinstance(pathway, AerialSpan)
        problems = []
        repairable = True
        for side in SIDES:
            geom, _kind = pathway.anchor_geometry(side)
            if geom is None:
                if is_aerial:
                    problems.append(f"{side} vertex is not attached to a structure")
                    repairable = False
                continue
            end = end_point(pathway.path, side)
            if not attaches(geom, end, ENDPOINT_TOLERANCE):
                distance = landing_on(geom, end).distance(end)
                problems.append(f"{side} vertex is {distance:.2f} from its anchor")
        vertices = len(pathway.path.coords)
        if is_aerial and vertices > 2:
            problems.append(f"aerial span has {vertices} vertices, not 2")
        if problems:
            found.append(Drift(pathway, problems, repairable))
    return found


def repair(pathway):
    """Land each attached end on its anchor and straighten aerial spans.

    The geometry the anchor had before the bulk write is unknown here, so an
    end on an area structure goes to the nearest point of its boundary.
    Junction branches of a repaired conduit follow it.
    """
    placements = {}
    for side in SIDES:
        geom, _kind = pathway.anchor_geometry(side)
        if geom is not None:
            placements[side] = landing_on(geom, end_point(pathway.path, side))
    _rewrite(pathway, placements)
    _cascade_junctions([pathway])
