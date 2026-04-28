import pytest
from django.contrib.gis.geos import LineString, Point, Polygon
from django.core.exceptions import ValidationError

from netbox_pathways.forms import ConduitBankForm, PathwayForm, PathwaysMapWidget
from netbox_pathways.geo import get_srid, to_leaflet
from netbox_pathways.models import Conduit, ConduitJunction, Pathway, Structure

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
    pw.pathway_type = "conduit"
    return pw


@pytest.mark.django_db
class TestPathwayEndpointValidation:
    def test_point_structure_within_tolerance_snaps(self):
        struct = _make_structure("S1", Point(100, 200, srid=SRID))
        path = LineString((100.5, 200.5), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()
        assert pw.path.coords[0] == (100.0, 200.0)

    def test_point_structure_beyond_tolerance_raises(self):
        struct = _make_structure("S2", Point(100, 200, srid=SRID))
        path = LineString((110, 210), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        with pytest.raises(ValidationError, match="start.*structure"):
            pw.clean()

    def test_end_structure_validated(self):
        struct = _make_structure("S3", Point(500, 500, srid=SRID))
        path = LineString((0, 0), (500.3, 500.3), srid=SRID)
        pw = _make_pathway(path, end_structure=struct)
        pw.clean()
        assert pw.path.coords[-1] == (500.0, 500.0)

    def test_no_structure_skips_validation(self):
        path = LineString((0, 0), (500, 500), srid=SRID)
        pw = _make_pathway(path)
        pw.clean()

    def test_no_path_skips_validation(self):
        struct = _make_structure("S4", Point(100, 200, srid=SRID))
        pw = _make_pathway(path=None, start_structure=struct)
        pw.clean()

    def test_polygon_structure_inside_snaps_to_boundary(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure("Poly1", poly)
        path = LineString((50, 50), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()
        snapped = Point(pw.path.coords[0][0], pw.path.coords[0][1], srid=SRID)
        assert struct.location.boundary.distance(snapped) < 0.01

    def test_polygon_structure_on_boundary_snaps(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure("Poly2", poly)
        path = LineString((50, 0), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()

    def test_polygon_structure_near_boundary_snaps(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure("Poly3", poly)
        path = LineString((50, -0.5), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        pw.clean()
        snapped = Point(pw.path.coords[0][0], pw.path.coords[0][1], srid=SRID)
        assert struct.location.boundary.distance(snapped) < 0.01

    def test_polygon_structure_far_outside_raises(self):
        poly = Polygon(((0, 0), (100, 0), (100, 100), (0, 100), (0, 0)), srid=SRID)
        struct = _make_structure("Poly4", poly)
        path = LineString((50, -5), (500, 500), srid=SRID)
        pw = _make_pathway(path, start_structure=struct)
        with pytest.raises(ValidationError, match="start.*structure"):
            pw.clean()

    def test_both_endpoints_snapped(self):
        s1 = _make_structure("Both1", Point(100, 200, srid=SRID))
        s2 = _make_structure("Both2", Point(500, 600, srid=SRID))
        path = LineString((100.3, 200.4), (300, 400), (500.2, 600.1), srid=SRID)
        pw = _make_pathway(path, start_structure=s1, end_structure=s2)
        pw.clean()
        assert pw.path.coords[0] == (100.0, 200.0)
        assert pw.path.coords[-1] == (500.0, 600.0)
        assert len(pw.path.coords) == 3


@pytest.mark.django_db
class TestConduitJunctionValidation:
    @pytest.fixture
    def trunk_setup(self):
        s1 = _make_structure("JS1", Point(0, 0, srid=SRID))
        s2 = _make_structure("JS2", Point(1000, 0, srid=SRID))
        trunk = Conduit(
            path=LineString((0, 0), (1000, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        trunk.pathway_type = "conduit"
        trunk.save()
        branch = Conduit(
            path=LineString((500, 100), (500, 500), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        branch.pathway_type = "conduit"
        branch.save()
        junction = ConduitJunction.objects.create(
            trunk_conduit=trunk,
            branch_conduit=branch,
            towards_structure=s1,
            position_on_trunk=0.5,
        )
        return s1, s2, trunk, junction

    def test_junction_within_tolerance_snaps(self, trunk_setup):
        s1, s2, trunk, junction = trunk_setup
        c = Conduit(
            path=LineString((500.5, 0.3), (1000, 0), srid=SRID),
            start_junction=junction,
            end_structure=s2,
        )
        c.pathway_type = "conduit"
        c.clean()
        assert abs(c.path.coords[0][0] - 500.0) < 0.01
        assert abs(c.path.coords[0][1] - 0.0) < 0.01

    def test_junction_beyond_tolerance_raises(self, trunk_setup):
        s1, s2, trunk, junction = trunk_setup
        c = Conduit(
            path=LineString((510, 10), (1000, 0), srid=SRID),
            start_junction=junction,
            end_structure=s2,
        )
        c.pathway_type = "conduit"
        with pytest.raises(ValidationError, match="start.*junction"):
            c.clean()


@pytest.mark.django_db
class TestPathAutoGeneration:
    def test_blank_path_with_two_point_structures_generates_line(self):
        s1 = _make_structure("AG1", Point(100, 200, srid=SRID))
        s2 = _make_structure("AG2", Point(500, 600, srid=SRID))
        form = PathwayForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["path"] is not None
        coords = form.cleaned_data["path"].coords
        assert len(coords) == 2

    def test_blank_path_with_polygon_structures_generates_centroid_line(self):
        poly1 = Polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)), srid=SRID)
        poly2 = Polygon(((100, 100), (110, 100), (110, 110), (100, 110), (100, 100)), srid=SRID)
        s1 = _make_structure("AG3", poly1)
        s2 = _make_structure("AG4", poly2)
        form = PathwayForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        path = form.cleaned_data["path"]
        assert path is not None
        assert len(path.coords) == 2

    def test_blank_path_with_only_one_structure_errors(self):
        s1 = _make_structure("AG5", Point(100, 200, srid=SRID))
        form = PathwayForm(
            data={
                "start_structure": s1.pk,
                "tags": [],
            }
        )
        assert not form.is_valid()
        assert "path" in form.errors or "__all__" in form.errors

    def test_blank_path_no_structures_errors(self):
        form = PathwayForm(data={"tags": []})
        assert not form.is_valid()

    def test_provided_path_not_overwritten(self):
        s1 = _make_structure("AG6", Point(100, 200, srid=SRID))
        s2 = _make_structure("AG7", Point(500, 600, srid=SRID))
        path = LineString((100, 200), (300, 400), (500, 600), srid=SRID)
        path_4326 = to_leaflet(path)
        form = PathwayForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "path": path_4326.geojson,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        assert len(form.cleaned_data["path"].coords) == 3


class TestWidgetEndpointRendering:
    def test_renders_endpoint_script_tag(self):
        widget = PathwaysMapWidget()
        widget.endpoint_geojson = {
            "start": {"type": "Point", "coordinates": [-73.5, 45.5]},
        }
        html = widget.render("path", None, attrs={"id": "id_path"})
        assert 'id="id_path-endpoints"' in html
        assert "application/json" in html
        assert "-73.5" in html

    def test_no_endpoint_data_no_script_tag(self):
        widget = PathwaysMapWidget()
        widget.endpoint_geojson = None
        html = widget.render("path", None, attrs={"id": "id_path"})
        assert "-endpoints" not in html


@pytest.mark.django_db
class TestEndToEndFormSave:
    def test_conduit_bank_form_generates_and_snaps(self):
        s1 = _make_structure("E2E1", Point(100, 200, srid=SRID))
        s2 = _make_structure("E2E2", Point(500, 600, srid=SRID))
        form = ConduitBankForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.pk is not None
        assert obj.path is not None
        assert obj.path.coords[0] == (100.0, 200.0)
        assert obj.path.coords[-1] == (500.0, 600.0)

    def test_form_with_drawn_path_snaps_on_save(self):
        s1 = _make_structure("E2E3", Point(100, 200, srid=SRID))
        s2 = _make_structure("E2E4", Point(500, 600, srid=SRID))
        path = LineString((100.3, 200.4), (300, 400), (500.2, 600.1), srid=SRID)
        path_4326 = to_leaflet(path)
        form = PathwayForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "path": path_4326.geojson,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.path.coords[0] == (100.0, 200.0)
        assert obj.path.coords[-1] == (500.0, 600.0)
        assert len(obj.path.coords) == 3
