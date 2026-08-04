"""
Cable route validation.

Checks whether a cable's route (sequence of CableSegments) is physically
connected — each consecutive pair of pathways must share a common endpoint
(Structure, Location, or ConduitJunction).
"""

from django.db.models import OuterRef, Subquery

from . import models
from .graph import _endpoint_nodes


def validate_cable_route(cable_id):
    """
    Validate that a cable's route is physically connected.

    Returns dict with:
        valid: bool — True if route is complete (no gaps)
        segment_count: int
        gaps: list of gap dicts
        ends: {"a": status, "b": status} -- whether the route's first and last
            segments reach the cable's own ends. Each status is "ok",
            "mismatch", or "unverified" when that cable end cannot be placed
            in the plant. Advisory only; it does not affect `valid`.
    """
    # Annotate conduit junction endpoints via subquery (same pattern as graph.py)
    conduit_qs = models.Conduit.objects.filter(pathway_ptr_id=OuterRef("pathway_id"))
    segments = list(
        models.CableSegment.objects.filter(cable_id=cable_id)
        .select_related(
            "pathway",
            "pathway__start_structure",
            "pathway__end_structure",
            "pathway__start_location",
            "pathway__end_location",
        )
        .annotate(
            _start_junction_id=Subquery(conduit_qs.values("start_junction_id")[:1]),
            _end_junction_id=Subquery(conduit_qs.values("end_junction_id")[:1]),
        )
        .order_by("sequence")
    )

    segment_count = len(segments)
    if segment_count == 0:
        return {"valid": False, "segment_count": 0, "gaps": [], "ends": _end_statuses(cable_id, segments)}

    if segment_count == 1:
        pw = segments[0].pathway
        if pw is None:
            return {
                "valid": False,
                "segment_count": 1,
                "gaps": [_null_gap(segments[0], None)],
                "ends": _end_statuses(cable_id, segments),
            }
        return {
            "valid": True,
            "segment_count": 1,
            "gaps": [],
            "ends": _end_statuses(cable_id, segments),
        }

    gaps = []
    for i in range(len(segments) - 1):
        cur = segments[i]
        nxt = segments[i + 1]

        if cur.pathway is None or nxt.pathway is None:
            gaps.append(_null_gap(cur, nxt))
            continue

        # Transfer junction annotations to pathway objects for _endpoint_nodes
        cur.pathway._start_junction_id = cur._start_junction_id
        cur.pathway._end_junction_id = cur._end_junction_id
        nxt.pathway._start_junction_id = nxt._start_junction_id
        nxt.pathway._end_junction_id = nxt._end_junction_id

        cur_start, cur_end = _endpoint_nodes(cur.pathway)
        nxt_start, nxt_end = _endpoint_nodes(nxt.pathway)

        cur_endpoints = {n for n in (cur_start, cur_end) if n}
        nxt_endpoints = {n for n in (nxt_start, nxt_end) if n}

        if not cur_endpoints & nxt_endpoints:
            gaps.append(
                {
                    "after_segment_id": cur.pk,
                    "before_segment_id": nxt.pk,
                    "after_pathway": str(cur.pathway),
                    "before_pathway": str(nxt.pathway),
                    "detail": (f"No shared endpoint between '{cur.pathway}' and '{nxt.pathway}'"),
                }
            )

    return {
        "valid": len(gaps) == 0,
        "segment_count": segment_count,
        "gaps": gaps,
        "ends": _end_statuses(cable_id, segments),
    }


def _null_gap(cur_seg, nxt_seg):
    return {
        "after_segment_id": cur_seg.pk,
        "before_segment_id": nxt_seg.pk if nxt_seg else None,
        "after_pathway": str(cur_seg.pathway) if cur_seg.pathway else None,
        "before_pathway": str(nxt_seg.pathway) if nxt_seg and nxt_seg.pathway else None,
        "detail": "Segment has no pathway assigned",
    }


def _end_statuses(cable_id, segments):
    """Whether the route's ends reach the cable's ends.

    Advisory only -- `valid` keeps meaning "no gaps between segments", because
    the pull sheet and the Route tab badge already depend on that meaning. The
    comparison is orientation-agnostic: a segment matches if either endpoint of
    its pathway is one of the cable end's candidate nodes.
    """
    from dcim.models import Cable

    from .anchors import cable_end_nodes

    statuses = {"a": "unverified", "b": "unverified"}
    if not segments:
        return statuses

    cable = Cable.objects.filter(pk=cable_id).first()
    if cable is None:
        return statuses

    for key, cable_end, segment in (("a", "A", segments[0]), ("b", "B", segments[-1])):
        candidates = set(cable_end_nodes(cable, cable_end).nodes)
        if not candidates:
            continue
        if segment.pathway is None:
            statuses[key] = "mismatch"
            continue
        segment.pathway._start_junction_id = segment._start_junction_id
        segment.pathway._end_junction_id = segment._end_junction_id
        endpoints = {node for node in _endpoint_nodes(segment.pathway) if node}
        statuses[key] = "ok" if endpoints & candidates else "mismatch"

    return statuses
