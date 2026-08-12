"""Tests for the pathway split service module.

Regression suite for issue #87: split one long imported polyline into
per-hop pathways between the structures it passes.
"""

import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, Structure
from netbox_pathways.split import SplitError, find_candidates

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
