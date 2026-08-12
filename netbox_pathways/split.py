"""Split a pathway at intermediate structures into per-hop children.

Geometry imported from KMZ files or other OSP tools often arrives as one
long polyline that physically passes many structures but is stored as a
single pathway, contributing a single edge to the adjacency graph. This
module detects the structures the polyline passes, cuts the geometry at
those points, and replaces the pathway with consecutive per-hop pathways.
"""

import math
from dataclasses import dataclass

from django.contrib.gis.geos import LineString

from .models import Structure

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
    vertex replaces that vertex rather than duplicating it.
    """
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
