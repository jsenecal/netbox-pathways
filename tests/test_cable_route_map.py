"""The cable Map tab: segments, cable-end markers, gaps and the highlighted segment."""

import pytest
from django.contrib.gis.geos import LineString
from django.test import RequestFactory

from netbox_pathways.geo import linestring_to_coords
from netbox_pathways.models import CableSegment, Conduit
from netbox_pathways.route_map import cable_route_geo
from netbox_pathways.views import CableRouteMapView
from tests.conftest import build_cable_with_terminations
from tests.helpers import SRID, make_conduit, make_pole


@pytest.fixture
def plant(db, _disable_routability_signal):
    """SA (site A) -- M -- N -- SB (site B), one conduit per hop; the cable runs site A -> site B."""
    from dcim.models import Site

    site_a = Site.objects.create(name="RM-A", slug="rm-a")
    site_b = Site.objects.create(name="RM-B", slug="rm-b")
    sa, m, n, sb = (
        make_pole("RM-SA", 0, 0),
        make_pole("RM-M", 100, 0),
        make_pole("RM-N", 200, 0),
        make_pole("RM-SB", 300, 0),
    )
    for structure, site in ((sa, site_a), (sb, site_b)):
        structure.site = site
        structure.save()
    hops = [
        make_conduit([(0, 0), (100, 0)], start_structure=sa, end_structure=m, label="RM-1"),
        make_conduit([(100, 0), (200, 0)], start_structure=m, end_structure=n, label="RM-2"),
        make_conduit([(200, 0), (300, 0)], start_structure=n, end_structure=sb, label="RM-3"),
    ]
    cable = build_cable_with_terminations(label="RM-cable", site=site_a, site_b=site_b)
    return {"cable": cable, "hops": hops, "SA": sa, "M": m, "N": n, "SB": sb}


def _route(cable, pathways):
    return [CableSegment.objects.create(cable=cable, pathway=p, sequence=i) for i, p in enumerate(pathways, 1)]


def _lines(geo, dashed=False):
    return [line for line in geo["lines"] if bool(line.get("dashed")) == dashed]


def test_one_numbered_line_per_segment_in_route_order(plant):
    segments = _route(plant["cable"], plant["hops"])

    lines = _lines(cable_route_geo(plant["cable"]))

    assert [(line["key"], line["label"]) for line in lines] == [
        (f"segment-{s.pk}", str(i)) for i, s in enumerate(segments, 1)
    ]
    assert {line["color"] for line in lines} == {"green"}


def test_cable_ends_are_marked_at_their_structures(plant):
    _route(plant["cable"], plant["hops"])

    points = {p["name"]: p for p in cable_route_geo(plant["cable"])["points"]}

    assert set(points) == {"Cable end A: RM-SA", "Cable end B: RM-SB"}
    assert (points["Cable end A: RM-SA"]["color"], points["Cable end B: RM-SB"]["color"]) == ("green", "red")


def test_a_gap_is_drawn_between_the_closest_ends_of_the_two_segments(plant):
    first, _middle, last = plant["hops"]
    _route(plant["cable"], [first, last])

    gaps = _lines(cable_route_geo(plant["cable"]), dashed=True)

    expected = linestring_to_coords(LineString((100, 0), (200, 0), srid=SRID))
    assert [(gap["coords"], gap["color"]) for gap in gaps] == [(expected, "red")]


def test_a_segment_that_misses_its_cable_end_is_flagged(plant):
    _first, middle, last = plant["hops"]
    segments = _route(plant["cable"], [middle, last])

    colors = {line["key"]: line["color"] for line in _lines(cable_route_geo(plant["cable"]))}

    assert colors[f"segment-{segments[0].pk}"] == "orange"
    assert colors[f"segment-{segments[1].pk}"] != "orange"


def test_map_tab_is_hidden_without_drawable_segments(plant):
    assert CableRouteMapView.tab.badge(plant["cable"]) is None

    indoor = Conduit(start_structure=plant["SA"], end_structure=plant["M"])
    indoor.save()
    _route(plant["cable"], [indoor])
    assert CableRouteMapView.tab.badge(plant["cable"]) is None

    CableSegment.objects.create(cable=plant["cable"], pathway=plant["hops"][0], sequence=2)
    assert CableRouteMapView.tab.badge(plant["cable"]) == 1


@pytest.mark.parametrize("own_segment", [True, False])
def test_segment_query_param_highlights_only_this_cables_segments(plant, own_segment):
    segments = _route(plant["cable"], plant["hops"])
    other_cable = build_cable_with_terminations(label="RM-other", site=plant["cable"].terminations.first()._site)
    foreign = CableSegment.objects.create(cable=other_cable, pathway=plant["hops"][0], sequence=1)
    target = segments[1] if own_segment else foreign

    request = RequestFactory().get("/", {"segment": target.pk})
    context = CableRouteMapView().get_extra_context(request, plant["cable"])

    assert context["highlight_key"] == (f"segment-{target.pk}" if own_segment else None)


def test_a_cable_end_at_a_building_is_drawn_as_its_outline(plant):
    from tests.helpers import square

    plant["SB"].geometry = square(300, -5, size=10)
    plant["SB"].save()
    _route(plant["cable"], plant["hops"][:2])

    geo = cable_route_geo(plant["cable"])

    assert [p["name"] for p in geo["polygons"]] == ["Cable end B: RM-SB"]


def test_segment_page_links_its_neighbours_in_route_order(plant):
    from netbox_pathways.views import CableSegmentView

    first, middle, last = _route(plant["cable"], plant["hops"])

    context = CableSegmentView().get_extra_context(RequestFactory().get("/"), middle)

    assert (context["prev_segment"], context["next_segment"], context["segment_ordinal"]) == (first, last, 2)


def test_pull_sheet_lists_the_route_in_order(plant, client, admin_user):
    _route(plant["cable"], list(reversed(plant["hops"])))
    client.force_login(admin_user)

    content = client.get(f"/plugins/pathways/pull-sheets/{plant['cable'].pk}/").content.decode()

    assert content.index("RM-3") < content.index("RM-2") < content.index("RM-1")


def test_segments_without_a_drawn_path_are_skipped_but_keep_the_numbering(plant):
    """Map labels must match the Route table's row numbers even past an indoor run."""
    indoor = Conduit(start_structure=plant["SA"], end_structure=plant["M"])
    indoor.save()
    segments = _route(plant["cable"], [indoor, plant["hops"][1]])

    lines = _lines(cable_route_geo(plant["cable"]))

    assert [(line["key"], line["label"]) for line in lines] == [(f"segment-{segments[1].pk}", "2")]
