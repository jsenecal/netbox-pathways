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
    """
    # Annotate conduit junction endpoints via subquery (same pattern as graph.py)
    conduit_qs = models.Conduit.objects.filter(
        pathway_ptr_id=OuterRef('pathway_id')
    )
    segments = list(
        models.CableSegment.objects
        .filter(cable_id=cable_id)
        .select_related(
            'pathway',
            'pathway__start_structure',
            'pathway__end_structure',
            'pathway__start_location',
            'pathway__end_location',
        )
        .annotate(
            _start_junction_id=Subquery(
                conduit_qs.values('start_junction_id')[:1]
            ),
            _end_junction_id=Subquery(
                conduit_qs.values('end_junction_id')[:1]
            ),
        )
        .order_by('sequence')
    )

    segment_count = len(segments)
    if segment_count == 0:
        return {'valid': False, 'segment_count': 0, 'gaps': []}

    if segment_count == 1:
        pw = segments[0].pathway
        if pw is None:
            return {
                'valid': False, 'segment_count': 1,
                'gaps': [_null_gap(segments[0], None)],
            }
        return {'valid': True, 'segment_count': 1, 'gaps': []}

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
            gaps.append({
                'after_segment_id': cur.pk,
                'before_segment_id': nxt.pk,
                'after_pathway': str(cur.pathway),
                'before_pathway': str(nxt.pathway),
                'detail': (
                    f"No shared endpoint between "
                    f"'{cur.pathway}' and '{nxt.pathway}'"
                ),
            })

    return {
        'valid': len(gaps) == 0,
        'segment_count': segment_count,
        'gaps': gaps,
    }


def _null_gap(cur_seg, nxt_seg):
    return {
        'after_segment_id': cur_seg.pk,
        'before_segment_id': nxt_seg.pk if nxt_seg else None,
        'after_pathway': str(cur_seg.pathway) if cur_seg.pathway else None,
        'before_pathway': str(nxt_seg.pathway) if nxt_seg and nxt_seg.pathway else None,
        'detail': 'Segment has no pathway assigned',
    }
