"""Map data for a cable's route: its segments, its two ends, and the gaps between.

Feeds the cable Map tab (views.CableRouteMapView) through the shared
inc/geo_map_panel.html, in the same {points, lines, polygons} shape the other
detail maps use. Each segment line carries a `key` so a Route tab row can link
to the Map tab with that segment highlighted, and a `label` with its position
in the route.
"""

from django.contrib.gis.geos import LineString

from . import models
from .anchors import cable_end_nodes
from .geo import linestring_to_coords
from .landing import end_point
from .map_data import add_structure, pathway_line
from .routing import validate_cable_route

END_COLORS = {"A": "green", "B": "red"}
COMPLETE_COLOR = "green"
MISMATCH_COLOR = "orange"
GAP_COLOR = "red"


def segment_key(segment_pk):
    """The map key of a segment's line; also what ?segment= highlights."""
    return f"segment-{segment_pk}"


def cable_route_geo(cable):
    """Inline map data for `cable`'s route.

    Segments are numbered in route order and coloured green when the route is
    complete; a first or last segment that does not reach its cable end is
    orange. Each gap between two drawn segments is a dashed red line between
    their closest ends. Each cable end is a marker (A green, B red) at the
    most precise structure that end resolves to (a building as its outline).
    """
    route = validate_cable_route(cable.pk)
    segments = route["segments"]
    data = {"points": [], "lines": [], "polygons": []}
    mismatched = {route["end_segments"][end] for end, status in route["ends"].items() if status == "mismatch"}

    drawn = {}
    for ordinal, segment in enumerate(segments, 1):
        line = pathway_line(segment.pathway) if segment.pathway else None
        if line is None:
            continue
        line["key"] = segment_key(segment.pk)
        line["label"] = str(ordinal)
        if segment.pk in mismatched:
            line["color"] = MISMATCH_COLOR
        elif route["valid"]:
            line["color"] = COMPLETE_COLOR
        data["lines"].append(line)
        drawn[segment.pk] = segment.pathway.path

    for gap in route["gaps"]:
        after, before = drawn.get(gap["after_segment_id"]), drawn.get(gap["before_segment_id"])
        if after is not None and before is not None:
            data["lines"].append(_gap_line(after, before, gap["detail"]))

    for end, color in END_COLORS.items():
        candidates = cable_end_nodes(cable, end).structures
        structure = models.Structure.objects.filter(pk=candidates[0]).first() if candidates else None
        if structure is not None:
            add_structure(data, structure, color=color, name=f"Cable end {end}: {structure.name}")

    return data


def _gap_line(path_a, path_b, detail):
    """A dashed line joining the closest pair of ends of two disconnected paths."""
    pairs = [(end_point(path_a, a), end_point(path_b, b)) for a in ("start", "end") for b in ("start", "end")]
    near_a, near_b = min(pairs, key=lambda pair: pair[0].distance(pair[1]))
    line = LineString((near_a.x, near_a.y), (near_b.x, near_b.y), srid=path_a.srid)
    return {"coords": linestring_to_coords(line), "name": detail, "color": GAP_COLOR, "dashed": True}
