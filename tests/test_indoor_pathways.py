"""Tests for pathless indoor (location-to-location) pathways.

A pathway whose both endpoints are dcim.Locations is indoor: locations carry
no geometry, so no geographic path can exist for it. `path` must be optional
in that case and remain required whenever a geographic endpoint (structure or
junction) is set.
"""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString, Point
from django.core.exceptions import ValidationError

from netbox_pathways.forms import ConduitForm, InnerductForm
from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, ConduitJunction, Structure

SRID = get_srid()


@pytest.fixture
def locations(db):
    site = Site.objects.create(name="Indoor Site", slug="indoor-site")
    loc_a = Location.objects.create(site=site, name="Room A", slug="room-a")
    loc_b = Location.objects.create(site=site, name="Room B", slug="room-b")
    return loc_a, loc_b


def _make_structure(name, geom):
    return Structure.objects.create(name=name, location=geom)


def _make_conduit(**kwargs):
    c = Conduit(**kwargs)
    c.pathway_type = "conduit"
    return c


@pytest.mark.django_db
class TestIndoorPathwayModelValidation:
    def test_location_to_location_conduit_without_path_validates(self, locations):
        loc_a, loc_b = locations
        c = _make_conduit(start_location=loc_a, end_location=loc_b)
        c.full_clean()
        c.save()
        assert c.pk is not None
        assert c.path is None

    def test_structure_endpoint_without_path_raises(self, locations):
        _, loc_b = locations
        s1 = _make_structure("IP1", Point(0, 0, srid=SRID))
        c = _make_conduit(start_structure=s1, end_location=loc_b)
        with pytest.raises(ValidationError) as exc:
            c.full_clean()
        assert "path" in exc.value.message_dict

    def test_junction_endpoint_without_path_raises(self, locations):
        _, loc_b = locations
        s1 = _make_structure("IP2", Point(0, 0, srid=SRID))
        s2 = _make_structure("IP3", Point(1000, 0, srid=SRID))
        trunk = _make_conduit(
            path=LineString((0, 0), (1000, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        trunk.save()
        branch = _make_conduit(
            path=LineString((500, 100), (500, 500), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        branch.save()
        junction = ConduitJunction.objects.create(
            trunk_conduit=trunk,
            branch_conduit=branch,
            towards_structure=s1,
            position_on_trunk=0.5,
        )
        c = _make_conduit(start_junction=junction, end_location=loc_b)
        with pytest.raises(ValidationError) as exc:
            c.full_clean()
        assert "path" in exc.value.message_dict


@pytest.mark.django_db
class TestIndoorPathwayForms:
    def test_conduit_form_between_two_locations_is_valid(self, locations):
        loc_a, loc_b = locations
        form = ConduitForm(
            data={
                "start_location": loc_a.pk,
                "end_location": loc_b.pk,
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.pk is not None
        assert obj.path is None

    def test_conduit_form_structure_and_location_without_path_errors(self, locations):
        _, loc_b = locations
        s1 = _make_structure("IPF1", Point(0, 0, srid=SRID))
        form = ConduitForm(
            data={
                "start_structure": s1.pk,
                "end_location": loc_b.pk,
                "tags": [],
            }
        )
        assert not form.is_valid()
        assert "path" in form.errors

    def test_innerduct_form_inherits_indoor_parent_locations(self, locations):
        loc_a, loc_b = locations
        parent = _make_conduit(start_location=loc_a, end_location=loc_b)
        parent.save()
        form = InnerductForm(
            data={
                "parent_conduit": parent.pk,
                "size": "32mm",
                "tags": [],
            }
        )
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.path is None
        assert obj.start_location == loc_a
        assert obj.end_location == loc_b


@pytest.mark.django_db
class TestIndoorGeoLayers:
    def test_indoor_conduit_excluded_from_geo_layers(self, locations):
        """Pathless indoor pathways must not appear in GeoJSON map layers."""
        from netbox_pathways.api.geo import ConduitGeoViewSet, PathwayGeoViewSet

        loc_a, loc_b = locations
        c = _make_conduit(start_location=loc_a, end_location=loc_b)
        c.save()
        assert not ConduitGeoViewSet.queryset.filter(pk=c.pk).exists()
        assert not PathwayGeoViewSet.queryset.filter(pk=c.pk).exists()
