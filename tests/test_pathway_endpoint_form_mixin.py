"""Tests for PathwayEndpointFormMixin.clean -- form-side auto-path generation."""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point, Polygon

from netbox_pathways.forms import PathwayForm
from netbox_pathways.geo import get_srid, to_leaflet
from netbox_pathways.models import Pathway, Structure

SRID = get_srid()


def _make_structure(name, geom):
    return Structure.objects.create(name=name, geometry=geom)


@pytest.mark.django_db
class TestPathwayEndpointFormMixinClean:
    def test_provided_path_is_kept(self):
        """If the user supplies a path, the mixin must not overwrite it."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        explicit_path = LineString((0, 0), (50, 50), (100, 100), srid=SRID)
        form = PathwayForm(
            data={
                "pathway_type": "conduit",
                "status": "active",
                "geometry": to_leaflet(explicit_path).geojson,
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        cleaned_path = form.cleaned_data["geometry"]
        assert len(cleaned_path.coords) == 3

    def test_aerial_span_form_without_path_lands_on_the_facing_wall(self):
        """Aerial spans derive their own path; the mixin must not synthesize a centroid line."""
        building = _make_structure("AF-B", Polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)), srid=SRID))
        pole = _make_structure("AF-P", Point(60, 3, srid=SRID))
        form = PathwayForm(
            data={
                "pathway_type": "aerial",
                "status": "active",
                "start_structure": building.pk,
                "end_structure": pole.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        assert [(round(x, 6), round(y, 6)) for x, y in form.instance.geometry.coords] == [(10.0, 3.0), (60.0, 3.0)]

    def test_missing_path_auto_generates_from_point_structures(self):
        """When both structures are points and no path is given, the mixin
        must construct a straight LineString between the two points."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        form = PathwayForm(
            data={
                "pathway_type": "conduit",
                "status": "active",
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        cleaned_path = form.cleaned_data["geometry"]
        assert cleaned_path.coords == ((0.0, 0.0), (100.0, 100.0))

    def test_missing_path_uses_polygon_centroid(self):
        """When a structure is a polygon, the mixin uses its centroid."""
        poly = Polygon(((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)), srid=SRID)
        s1 = _make_structure("S1", poly)
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        form = PathwayForm(
            data={
                "pathway_type": "conduit",
                "status": "active",
                "start_structure": s1.pk,
                "end_structure": s2.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        start_pt = form.cleaned_data["geometry"].coords[0]
        # centroid of the square (0,0)-(10,10) is (5, 5)
        assert start_pt == (5.0, 5.0)

    def test_innerduct_gets_no_synthetic_path(self):
        """Contained pathways own no geometry: an innerduct with a blank path
        stays pathless instead of receiving a straight line between the
        parent's structures. Behavior change for issue #77."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        parent = Pathway(
            pathway_type="conduit",
            label="C1",
            geometry=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        parent.save()
        form = PathwayForm(
            data={
                "pathway_type": "innerduct",
                "status": "active",
                "parent": parent.pk,
                "size": "32mm",
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["geometry"] is None

    def test_bank_conduit_gets_no_synthetic_path(self):
        """A conduit created inside a bank stays pathless: the bank owns the
        route geometry. Behavior change for issue #77."""
        s1 = _make_structure("S1", Point(0, 0, srid=SRID))
        s2 = _make_structure("S2", Point(100, 100, srid=SRID))
        bank = Pathway(
            pathway_type="conduit_bank",
            label="BANK-1",
            geometry=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        bank.save()
        form = PathwayForm(
            data={
                "pathway_type": "conduit",
                "status": "active",
                "parent": bank.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        assert form.cleaned_data["geometry"] is None

    def test_no_path_no_structures_raises_validation_error(self):
        """Without a path and without structures, the mixin must reject."""
        form = PathwayForm(data={"pathway_type": "conduit", "tags": []})
        assert not form.is_valid()
        assert "geometry" in form.errors


@pytest.mark.django_db
class TestInjectEndpointGeometry:
    def test_injects_geometry_and_names(self):
        """The widget payload must carry each endpoint's name so the map can
        label the locked markers like it labels reference structures."""
        s1 = _make_structure("MH-100", Point(0, 0, srid=SRID))
        s2 = _make_structure("MH-200", Point(100, 100, srid=SRID))
        conduit = Pathway(
            pathway_type="conduit",
            label="C1",
            geometry=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        conduit.save()

        form = PathwayForm(instance=conduit)
        data = form.fields["geometry"].widget.endpoint_geojson
        assert data["start"]["type"] == "Point"
        assert data["end"]["type"] == "Point"
        assert data["start_name"] == "MH-100"
        assert data["end_name"] == "MH-200"

    def test_no_endpoints_injects_nothing(self):
        form = PathwayForm(initial={"pathway_type": "conduit"})
        assert form.fields["geometry"].widget.endpoint_geojson is None

    def test_aerial_span_form_requests_straight_mode(self):
        form = PathwayForm(initial={"pathway_type": "aerial"})
        assert form.fields["geometry"].widget.endpoint_geojson == {"straight": True}

    def test_location_identity_structure_is_injected(self):
        site = Site.objects.create(name="Inj-Site", slug="inj-site")
        loc = Location.objects.create(name="Inj-Loc", slug="inj-loc", site=site)
        Structure.objects.create(name="Vault-9", geometry=Point(0, 0, srid=SRID), location=loc)
        conduit = Pathway(pathway_type="conduit", start_location=loc, geometry=LineString((0, 0), (10, 0), srid=SRID))

        form = PathwayForm(instance=conduit)

        data = form.fields["geometry"].widget.endpoint_geojson
        assert data["start_name"] == "Vault-9"
        assert "end" not in data
