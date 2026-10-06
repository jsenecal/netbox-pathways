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
        end_segments: {"a": pk, "b": pk} -- the segment each `ends` status
            judges (None when the cable has no segments).
        segments: the CableSegments in route order, as validated.
    """
    # Annotate conduit junction endpoints via subquery (same pattern as graph.py)
    conduit_qs = models.Conduit.objects.filter(pathway_ptr_id=OuterRef("pathway_id"))
    segments = list(
        models.CableSegment.objects.route_of(cable_id).annotate(
            _start_junction_id=Subquery(conduit_qs.values("start_junction_id")[:1]),
            _end_junction_id=Subquery(conduit_qs.values("end_junction_id")[:1]),
        )
    )

    segment_count = len(segments)
    if segment_count == 0:
        return _result(cable_id, segments, [])

    if segment_count == 1:
        gaps = [_null_gap(segments[0], None)] if segments[0].pathway is None else []
        return _result(cable_id, segments, gaps)

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

    return _result(cable_id, segments, gaps)


def _result(cable_id, segments, gaps):
    """The validate_cable_route() result for `segments` (in route order) and their `gaps`."""
    return {
        "valid": bool(segments) and not gaps,
        "segment_count": len(segments),
        "gaps": gaps,
        "ends": _end_statuses(cable_id, segments),
        # The segment each end status is about: the first faces end A, the last end B.
        "end_segments": {
            "a": segments[0].pk if segments else None,
            "b": segments[-1].pk if segments else None,
        },
        "segments": segments,
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
