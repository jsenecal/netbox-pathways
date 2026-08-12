"""Tests for the pathway split service module.

Regression suite for issue #87: split one long imported polyline into
per-hop pathways between the structures it passes.
"""

import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, Structure
from netbox_pathways.split import SplitError, _cut_line, find_candidates

SRID = get_srid()


def _structure(name, x, y):
    return Structure.objects.create(name=name, geometry=Point(x, y, srid=SRID))


def _span(start, end, path, **kwargs):
    return AerialSpan.objects.create(
        path=path,
        start_structure=start,
        end_structure=end,
        **kwargs,
    )


@pytest.mark.django_db
class TestFindCandidates:
    def test_orders_by_chainage_excludes_endpoints_and_out_of_tolerance(self):
        start = _structure("FC-A", 0, 0)
        end = _structure("FC-B", 300, 0)
        near_far_along = _structure("FC-mid2", 200, 0.5)
        near_early = _structure("FC-mid1", 100, -0.4)
        _structure("FC-off", 150, 50)  # 50 units off the line: not a candidate
        span = _span(start, end, LineString((0, 0), (300, 0), srid=SRID))

        candidates = find_candidates(span, tolerance=1.0)

        assert [c.structure.pk for c in candidates] == [near_early.pk, near_far_along.pk]
        assert candidates[0].chainage == pytest.approx(100.0)
        assert candidates[0].offset == pytest.approx(0.4)
        assert candidates[1].chainage == pytest.approx(200.0)

    def test_pathway_without_path_raises(self):
        span = AerialSpan(path=None)
        with pytest.raises(SplitError, match="path"):
            find_candidates(span, tolerance=1.0)


class TestCutLine:
    """Pure-geometry tests; no DB needed."""

    def test_vertices_land_in_the_right_children(self):
        line = LineString((0, 0), (100, 0), (200, 0), (300, 0), (400, 0), (500, 0), srid=SRID)
        cuts = [
            (150.0, Point(150, 0, srid=SRID)),
            (350.0, Point(350, 0, srid=SRID)),
        ]
        pieces = _cut_line(line, cuts)
        assert [tuple(p.coords) for p in pieces] == [
            ((0.0, 0.0), (100.0, 0.0), (150.0, 0.0)),
            ((150.0, 0.0), (200.0, 0.0), (300.0, 0.0), (350.0, 0.0)),
            ((350.0, 0.0), (400.0, 0.0), (500.0, 0.0)),
        ]

    def test_cut_on_existing_vertex_replaces_it(self):
        line = LineString((0, 0), (100, 0), (200, 0), srid=SRID)
        # Structure sits 0.3 off the drawn vertex; the vertex is replaced by
        # the structure point, not duplicated (no zero-length segment).
        pieces = _cut_line(line, [(100.0, Point(100, 0.3, srid=SRID))])
        assert [tuple(p.coords) for p in pieces] == [
            ((0.0, 0.0), (100.0, 0.3)),
            ((100.0, 0.3), (200.0, 0.0)),
        ]

    def test_offline_cut_point_is_written_verbatim(self):
        line = LineString((0, 0), (300, 0), srid=SRID)
        pieces = _cut_line(line, [(150.0, Point(150, 0.4, srid=SRID))])
        assert tuple(pieces[0].coords) == ((0.0, 0.0), (150.0, 0.4))
        assert tuple(pieces[1].coords) == ((150.0, 0.4), (300.0, 0.0))

    def test_two_cuts_in_the_same_segment(self):
        line = LineString((0, 0), (300, 0), srid=SRID)
        pieces = _cut_line(line, [(100.0, Point(100, 0, srid=SRID)), (200.0, Point(200, 0, srid=SRID))])
        assert [tuple(p.coords) for p in pieces] == [
            ((0.0, 0.0), (100.0, 0.0)),
            ((100.0, 0.0), (200.0, 0.0)),
            ((200.0, 0.0), (300.0, 0.0)),
        ]

    def test_srid_preserved(self):
        line = LineString((0, 0), (300, 0), srid=SRID)
        pieces = _cut_line(line, [(150.0, Point(150, 0, srid=SRID))])
        assert all(p.srid == SRID for p in pieces)
