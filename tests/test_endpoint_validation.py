import pytest
from django.contrib.gis.geos import LineString, Point, Polygon
from django.core.exceptions import ValidationError

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, Structure

SRID = get_srid()


def _make_structure(name, geom):
    return Structure.objects.create(name=name, location=geom)


def _make_pathway(path, start_structure=None, end_structure=None, **kwargs):
    pw = Pathway(
        path=path,
        start_structure=start_structure,
        end_structure=end_structure,
        **kwargs,
    )
    pw.pathway_type = 'conduit'
    return pw


@pytest.mark.django_db
class TestPathwayEndpointValidation:
    def test_point_structure_within_tolerance_snaps(self):
        struct = _make_structure('S1', Point(100, 200, srid=SRID))
        path = LineString((100.5, 200.5), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()
        assert pw.path.coords[0] == (100.0, 200.0)

    def test_point_structure_beyond_tolerance_raises(self):
        struct = _make_structure('S2', Point(100, 200, srid=SRID))
        path = LineString((110, 210), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        with pytest.raises(ValidationError, match='start.*structure'):
            pw.clean()

    def test_end_structure_validated(self):
        struct = _make_structure('S3', Point(500, 500, srid=SRID))
        path = LineString((0, 0), (500.3, 500.3), srid=SRID)
        pw = _make_pathway(path, end_structure=struct)
        pw.clean()
        assert pw.path.coords[-1] == (500.0, 500.0)

    def test_no_structure_skips_validation(self):
        path = LineString((0, 0), (500, 500), srid=SRID)
        pw = _make_pathway(path)
        pw.clean()

    def test_no_path_skips_validation(self):
        struct = _make_structure('S4', Point(100, 200, srid=SRID))
        pw = _make_pathway(path=None, start_structure=struct)
        pw.clean()

    def test_polygon_structure_inside_snaps_to_boundary(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure('Poly1', poly)
        path = LineString((50, 50), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()
        snapped = Point(pw.path.coords[0][0], pw.path.coords[0][1], srid=SRID)
        assert struct.location.boundary.distance(snapped) < 0.01

    def test_polygon_structure_on_boundary_snaps(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure('Poly2', poly)
        path = LineString((50, 0), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()

    def test_polygon_structure_near_boundary_snaps(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure('Poly3', poly)
        path = LineString((50, -0.5), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()
        snapped = Point(pw.path.coords[0][0], pw.path.coords[0][1], srid=SRID)
        assert struct.location.boundary.distance(snapped) < 0.01

    def test_polygon_structure_far_outside_raises(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure('Poly4', poly)
        path = LineString((50, -5), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        with pytest.raises(ValidationError, match='start.*structure'):
            pw.clean()

    def test_both_endpoints_snapped(self):
        s1 = _make_structure('Both1', Point(100, 200, srid=SRID))
        s2 = _make_structure('Both2', Point(500, 600, srid=SRID))
        path = LineString((100.3, 200.4), (300, 400), (500.2, 600.1), srid=SRID)
        pw = _make_pathway(path, start_structure=s1, end_structure=s2)
        pw.clean()
        assert pw.path.coords[0] == (100.0, 200.0)
        assert pw.path.coords[-1] == (500.0, 600.0)
        assert len(pw.path.coords) == 3
