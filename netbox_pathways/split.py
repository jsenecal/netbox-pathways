"""Split a pathway at intermediate structures into per-hop children.

Geometry imported from KMZ files or other OSP tools often arrives as one
long polyline that physically passes many structures but is stored as a
single pathway, contributing a single edge to the adjacency graph. This
module detects the structures the polyline passes, cuts the geometry at
those points, and replaces the pathway with consecutive per-hop pathways.
"""

import math
from dataclasses import dataclass, field

from django.contrib.gis.geos import LineString

from .models import (
    AerialSpan,
    Conduit,
    ConduitBank,
    DirectBuried,
    Innerduct,
    PlannedRoute,
    Structure,
)

# A pathway endpoint or a neighbouring cut closer than this (in SRID units)
# collapses into one cut instead of producing a zero-length hop.
CUT_EPSILON = 1e-6

DEFAULT_TOLERANCE = 1.0


class SplitError(Exception):
    """Raised when a pathway cannot be split as requested."""


@dataclass
class Candidate:
    """A structure the polyline passes, positioned along it."""

    structure: Structure
    chainage: float
    offset: float


def find_candidates(pathway, tolerance=DEFAULT_TOLERANCE):
    """Structures within `tolerance` of the pathway's line, ordered by chainage.

    The pathway's own endpoint structures are excluded. Chainage is the
    distance along the line of the structure's projection (centroid for
    polygon footprints); offset is the structure's distance from the line.
    """
    if pathway.path is None:
        raise SplitError("Pathway has no geometry path; only pathways with a drawn path can be split.")
    line = pathway.path
    exclude_pks = [pk for pk in (pathway.start_structure_id, pathway.end_structure_id) if pk]
    queryset = Structure.objects.filter(geometry__dwithin=(line, tolerance)).exclude(pk__in=exclude_pks)
    candidates = [
        Candidate(
            structure=structure,
            chainage=line.project(structure.centroid),
            offset=structure.geometry.distance(line),
        )
        for structure in queryset
    ]
    candidates.sort(key=lambda c: c.chainage)
    return candidates


def _cut_line(line, cuts):
    """Cut a LineString at ordered (chainage, point) pairs into len(cuts)+1 pieces.

    Original vertices are preserved: each lands in exactly one piece
    according to its position along the line. Every cut vertex is written as
    the given point (the structure's own point), so endpoint snapping in
    Pathway.clean() is a no-op. A chainage coinciding with an existing
    vertex replaces that vertex rather than duplicating it. Cuts must be
    strictly interior: a chainage within CUT_EPSILON of either line end
    raises ValueError -- callers filter those out before cutting.
    """
    if cuts and (cuts[0][0] <= CUT_EPSILON or cuts[-1][0] >= line.length - CUT_EPSILON):
        raise ValueError("cuts must be strictly interior to the line (callers filter endpoint chainages)")
    coords = [(p[0], p[1]) for p in line.coords]
    remaining = list(cuts)
    pieces = []
    current = [coords[0]]
    walked = 0.0
    for seg_start, seg_end in zip(coords, coords[1:], strict=False):
        seg_end_chainage = walked + math.dist(seg_start, seg_end)
        replaces_vertex = False
        while remaining and remaining[0][0] <= seg_end_chainage + CUT_EPSILON:
            chainage, point = remaining.pop(0)
            cut_xy = (point.x, point.y)
            current.append(cut_xy)
            pieces.append(current)
            current = [cut_xy]
            replaces_vertex = abs(chainage - seg_end_chainage) <= CUT_EPSILON
        if not replaces_vertex:
            current.append(seg_end)
        walked = seg_end_chainage
    pieces.append(current)
    return [LineString(piece, srid=line.srid) for piece in pieces]


_TYPE_TO_MODEL = {
    "conduit_bank": ConduitBank,
    "conduit": Conduit,
    "aerial": AerialSpan,
    "direct_buried": DirectBuried,
    "innerduct": Innerduct,
}


@dataclass
class SplitPlan:
    """A validated split: concrete pathway, ordered cuts, prospective warnings."""

    pathway: object
    cuts: list
    warnings: list = field(default_factory=list)


def _concrete(pathway):
    """Resolve a base Pathway row to its MTI subclass instance."""
    cls = _TYPE_TO_MODEL.get(pathway.pathway_type)
    if cls is None or isinstance(pathway, cls):
        return pathway
    return cls.objects.get(pk=pathway.pk)


def _contained(original):
    """Dependent pathways that follow `original`'s route and cascade with it."""
    contained = []
    if isinstance(original, ConduitBank):
        for conduit in Conduit.objects.filter(conduit_bank=original):
            contained.append(conduit)
            contained.extend(Innerduct.objects.filter(parent_conduit=conduit))
    elif isinstance(original, Conduit):
        contained.extend(Innerduct.objects.filter(parent_conduit=original))
    return contained


def _check_splittable(original):
    if isinstance(original, Innerduct):
        raise SplitError("Innerducts follow their parent conduit; split the conduit instead.")
    if isinstance(original, Conduit) and original.conduit_bank_id:
        raise SplitError("This conduit is contained in a bank; split the conduit bank instead.")
    if original.path is None:
        raise SplitError("Pathway has no geometry path; only pathways with a drawn path can be split.")
    involved = [original, *_contained(original)]
    for pathway in involved:
        if not isinstance(pathway, Conduit):
            continue
        has_junctions = (
            pathway.start_junction_id
            or pathway.end_junction_id
            or pathway.junctions_on_trunk.exists()
            or pathway.junction_as_branch.exists()
        )
        if has_junctions:
            raise SplitError(
                f"Conduit {pathway} has junctions; splitting would invalidate their positions on the trunk."
            )


def _resolve_cuts(original, structures, tolerance, warnings):
    """Project structures onto the path; validate, order, and collapse them."""
    line = original.path
    entries = []
    for structure in structures:
        offset = structure.geometry.distance(line)
        if offset > tolerance:
            raise SplitError(f"Structure {structure} is {offset:.2f} SRID units from the path (tolerance {tolerance}).")
        chainage = line.project(structure.centroid)
        if chainage <= CUT_EPSILON or chainage >= line.length - CUT_EPSILON:
            warnings.append(f"Structure {structure} projects onto a path end; skipped.")
            continue
        entries.append(Candidate(structure=structure, chainage=chainage, offset=offset))
    entries.sort(key=lambda c: c.chainage)
    cuts = []
    for candidate in entries:
        if cuts and candidate.chainage - cuts[-1].chainage <= CUT_EPSILON:
            warnings.append(
                f"Structure {candidate.structure} coincides with {cuts[-1].structure}; collapsed into one cut."
            )
            continue
        cuts.append(candidate)
    return cuts


def plan_split(pathway, structures, tolerance=DEFAULT_TOLERANCE):
    """Validate a split and return the ordered cuts and prospective warnings.

    Shared by the dry-run preview and the apply path so both see exactly the
    same refusals and warnings.
    """
    original = _concrete(pathway)
    _check_splittable(original)
    warnings = []
    cuts = _resolve_cuts(original, structures, tolerance, warnings)
    if not cuts:
        raise SplitError("No usable split structures resolved.")
    for involved in [original, *_contained(original)]:
        waypoint_count = involved.waypoints.count()
        if waypoint_count:
            warnings.append(f"{waypoint_count} waypoint(s) on {involved} cannot be repositioned and will be deleted.")
        for route in PlannedRoute.objects.filter(pathway_ids__contains=[involved.pk]):
            warnings.append(
                f"Planned route #{route.pk} '{route.name}' references {involved}; re-plan it after the split."
            )
    return SplitPlan(pathway=original, cuts=cuts, warnings=warnings)
