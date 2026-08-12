"""Split a pathway at intermediate structures into per-hop children.

Geometry imported from KMZ files or other OSP tools often arrives as one
long polyline that physically passes many structures but is stored as a
single pathway, contributing a single edge to the adjacency graph. This
module detects the structures the polyline passes, cuts the geometry at
those points, and replaces the pathway with consecutive per-hop pathways.
"""

from dataclasses import dataclass

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
