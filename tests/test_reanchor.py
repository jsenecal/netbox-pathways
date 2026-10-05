"""Moving a structure drags the pathway ends attached to it."""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.models import Conduit, ConduitJunction, Pathway, Structure
from tests.helpers import SRID, coords, make_aerial_span, make_building, make_conduit, make_pole, square


def _move(structure, geom):
    structure.geometry = geom
    structure.save()


@pytest.mark.django_db
class TestReanchorOnStructureSave:
    def test_point_move_drags_conduit_end_and_keeps_interior_vertices(self):
        s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (50, 20), (100, 0)], start_structure=s1, end_structure=s2)

        _move(s2, Point(100, 30, srid=SRID))

        assert coords(conduit, refresh=True) == [(0.0, 0.0), (50.0, 20.0), (100.0, 30.0)]

    def test_aerial_span_is_rebuilt_straight_to_the_moved_pole(self):
        p1, p2 = make_pole("P1", 0, 0), make_pole("P2", 40, 0)
        span = make_aerial_span(p1, p2)

        _move(p2, Point(40, 25, srid=SRID))

        assert coords(span, refresh=True) == [(0.0, 0.0), (40.0, 25.0)]

    def test_translated_building_keeps_the_landing_on_the_same_wall(self):
        building = make_building("B1", 0, 0)
        pole = make_pole("P1", 60, 4)
        span = make_aerial_span(building, pole)
        assert coords(span, refresh=True)[0] == (10.0, 4.0)

        # Move the building 100 m east, past the pole: nearest-wall snapping
        # would jump to the west wall; the landing must stay on the east wall.
        _move(building, square(100, 0))

        assert coords(span, refresh=True) == [(110.0, 4.0), (60.0, 4.0)]

    def test_end_attached_through_location_identity_follows(self):
        site = Site.objects.create(name="RA-Site", slug="ra-site")
        loc = Location.objects.create(name="RA-Loc", slug="ra-loc", site=site)
        vault = Structure.objects.create(name="V1", geometry=Point(0, 0, srid=SRID), location=loc)
        far = make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (100, 0)], start_location=loc, end_structure=far)

        _move(vault, Point(0, 10, srid=SRID))

        assert coords(conduit, refresh=True)[0] == (0.0, 10.0)

    def test_branch_conduit_follows_its_junction_on_the_moved_trunk(self):
        s1, s2, s3 = make_pole("S1", 0, 0), make_pole("S2", 100, 0), make_pole("S3", 50, 50)
        trunk = make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
        branch = Conduit(path=LineString((50, 0), (50, 50), srid=SRID), end_structure=s3)
        branch.save()
        junction = ConduitJunction.objects.create(
            trunk_conduit=trunk, branch_conduit=branch, towards_structure=s2, position_on_trunk=0.5
        )
        branch.start_junction = junction
        branch.save()

        _move(s2, Point(100, 40, srid=SRID))

        assert coords(branch, refresh=True) == [(50.0, 20.0), (50.0, 50.0)]

    def test_both_ends_on_the_same_structure_both_move(self):
        s1 = make_pole("S1", 0, 0)
        loop = make_conduit([(0, 0), (10, 10), (0, 0)], start_structure=s1, end_structure=s1)

        _move(s1, Point(5, 0, srid=SRID))

        assert coords(loop, refresh=True) == [(5.0, 0.0), (10.0, 10.0), (5.0, 0.0)]

    def test_save_without_geometry_change_writes_no_pathway(self):
        s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
        before = Pathway.objects.get(pk=conduit.pk).last_updated

        s2.name = "S2-renamed"
        s2.save()

        assert Pathway.objects.get(pk=conduit.pk).last_updated == before


@pytest.mark.django_db
class TestReanchorEdgeCases:
    def test_geometry_in_another_srid_is_transformed_before_dragging_ends(self):
        """The REST API hands GeoJSON over as EPSG:4326 whatever the plugin SRID."""
        s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
        target = Point(100, 30, srid=SRID)
        wgs84 = target.transform(4326, clone=True)

        _move(s2, wgs84)

        end = coords(conduit, refresh=True)[-1]
        assert end == pytest.approx((100.0, 30.0), abs=1e-3)

    def test_save_with_update_fields_excluding_geometry_moves_nothing(self):
        s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
        conduit = make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)

        s2.geometry = Point(100, 30, srid=SRID)
        s2.name = "S2-renamed"
        s2.save(update_fields=["name"])

        assert coords(conduit, refresh=True)[-1] == (100.0, 0.0)

    def test_moving_the_support_of_a_legacy_detached_span_moves_its_attached_end(self):
        """A span saved without clean() may lack an end; its attached end still follows."""
        from netbox_pathways.models import AerialSpan

        pole = make_pole("LD-P1", 0, 0)
        span = AerialSpan(start_structure=pole, path=LineString((0, 0), (30, 0), srid=SRID))
        span.save()

        _move(pole, Point(0, 5, srid=SRID))

        assert coords(span, refresh=True) == [(0.0, 5.0), (30.0, 0.0)]
