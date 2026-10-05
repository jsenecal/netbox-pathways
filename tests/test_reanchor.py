"""Moving a structure drags the pathway ends attached to it."""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point, Polygon

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, Conduit, ConduitJunction, Pathway, Structure

SRID = get_srid()


def _pole(name, x, y):
    return Structure.objects.create(name=name, geometry=Point(x, y, srid=SRID))


def _square(x0, y0, size=10):
    ring = ((x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0))
    return Polygon(ring, srid=SRID)


def _conduit(path, **kwargs):
    conduit = Conduit(path=LineString(path, srid=SRID), **kwargs)
    conduit.save()
    return conduit


def _span(start, end):
    span = AerialSpan(start_structure=start, end_structure=end)
    span.full_clean()
    span.save()
    return span


def _move(structure, geom):
    structure.geometry = geom
    structure.save()


def _coords(pathway):
    pathway.refresh_from_db()
    return [(round(x, 6), round(y, 6)) for x, y in pathway.path.coords]


@pytest.mark.django_db
class TestReanchorOnStructureSave:
    def test_point_move_drags_conduit_end_and_keeps_interior_vertices(self):
        s1, s2 = _pole("S1", 0, 0), _pole("S2", 100, 0)
        conduit = _conduit([(0, 0), (50, 20), (100, 0)], start_structure=s1, end_structure=s2)

        _move(s2, Point(100, 30, srid=SRID))

        assert _coords(conduit) == [(0.0, 0.0), (50.0, 20.0), (100.0, 30.0)]

    def test_aerial_span_is_rebuilt_straight_to_the_moved_pole(self):
        p1, p2 = _pole("P1", 0, 0), _pole("P2", 40, 0)
        span = _span(p1, p2)

        _move(p2, Point(40, 25, srid=SRID))

        assert _coords(span) == [(0.0, 0.0), (40.0, 25.0)]

    def test_translated_building_keeps_the_landing_on_the_same_wall(self):
        building = Structure.objects.create(name="B1", geometry=_square(0, 0))
        pole = _pole("P1", 60, 4)
        span = _span(building, pole)
        assert _coords(span)[0] == (10.0, 4.0)

        # Move the building 100 m east, past the pole: nearest-wall snapping
        # would jump to the west wall; the landing must stay on the east wall.
        _move(building, _square(100, 0))

        assert _coords(span) == [(110.0, 4.0), (60.0, 4.0)]

    def test_end_attached_through_location_identity_follows(self):
        site = Site.objects.create(name="RA-Site", slug="ra-site")
        loc = Location.objects.create(name="RA-Loc", slug="ra-loc", site=site)
        vault = Structure.objects.create(name="V1", geometry=Point(0, 0, srid=SRID), location=loc)
        far = _pole("S2", 100, 0)
        conduit = _conduit([(0, 0), (100, 0)], start_location=loc, end_structure=far)

        _move(vault, Point(0, 10, srid=SRID))

        assert _coords(conduit)[0] == (0.0, 10.0)

    def test_branch_conduit_follows_its_junction_on_the_moved_trunk(self):
        s1, s2, s3 = _pole("S1", 0, 0), _pole("S2", 100, 0), _pole("S3", 50, 50)
        trunk = _conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
        branch = Conduit(path=LineString((50, 0), (50, 50), srid=SRID), end_structure=s3)
        branch.save()
        junction = ConduitJunction.objects.create(
            trunk_conduit=trunk, branch_conduit=branch, towards_structure=s2, position_on_trunk=0.5
        )
        branch.start_junction = junction
        branch.save()

        _move(s2, Point(100, 40, srid=SRID))

        assert _coords(branch) == [(50.0, 20.0), (50.0, 50.0)]

    def test_both_ends_on_the_same_structure_both_move(self):
        s1 = _pole("S1", 0, 0)
        loop = _conduit([(0, 0), (10, 10), (0, 0)], start_structure=s1, end_structure=s1)

        _move(s1, Point(5, 0, srid=SRID))

        assert _coords(loop) == [(5.0, 0.0), (10.0, 10.0), (5.0, 0.0)]

    def test_save_without_geometry_change_writes_no_pathway(self):
        s1, s2 = _pole("S1", 0, 0), _pole("S2", 100, 0)
        conduit = _conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
        before = Pathway.objects.get(pk=conduit.pk).last_updated

        s2.name = "S2-renamed"
        s2.save()

        assert Pathway.objects.get(pk=conduit.pk).last_updated == before
