"""Tests for PathwayEndpointFormMixin.clean -- form-side auto-path generation."""

import pytest
from django.contrib.gis.geos import LineString, Point, Polygon

from netbox_pathways.forms import ConduitForm, InnerductForm
from netbox_pathways.geo import get_srid, to_leaflet
from netbox_pathways.models import Conduit, Structure

SRID = get_srid()


def _make_structure(name, geom):
    return Structure.objects.create(name=name, location=geom)


@pytest.mark.django_db
class TestPathwayEndpointFormMixinClean:
    def test_provided_path_is_kept(self):
        """If the user supplies a path, the mixin must not overwrite it."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        explicit_path = LineString((0, 0), (50, 50), (100, 100), srid=SRID)
        form = ConduitForm(
            data={
                "path": to_leaflet(explicit_path).geojson,
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        cleaned_path = form.cleaned_data["path"]
        assert len(cleaned_path.coords) == 3

    def test_missing_path_auto_generates_from_point_structures(self):
        """When both structures are points and no path is given, the mixin
        must construct a straight LineString between the two points."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        form = ConduitForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        cleaned_path = form.cleaned_data["path"]
        assert cleaned_path.coords == ((0.0, 0.0), (100.0, 100.0))

    def test_missing_path_uses_polygon_centroid(self):
        """When a structure is a polygon, the mixin uses its centroid."""
        poly = Polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)), srid=SRID)
        s1 = _make_structure("S1", poly)
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        form = ConduitForm(
            data={
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        start_pt = form.cleaned_data["path"].coords[0]
        # centroid of the square (0,0)-(10,10) is (5, 5)
        assert start_pt == (5.0, 5.0)

    def test_innerduct_inherits_parent_conduit_structures(self):
        """Innerduct fallback: when structures are omitted, inherit from
        parent_conduit's start/end."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        parent = Conduit(
            label="C1",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        parent.pathway_type = "conduit"
        parent.save()
        form = InnerductForm(
            data={
                "parent_conduit": parent.pk,
                "size": "32mm",
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["path"] is not None

    def test_no_path_no_structures_raises_validation_error(self):
        """Without a path and without structures, the mixin must reject."""
        form = ConduitForm(data={"tags": []})
        assert not form.is_valid()
        assert "path" in form.errors
