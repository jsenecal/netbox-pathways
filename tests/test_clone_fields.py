"""Clone action pre-fill: per-model clone_fields declarations.

Regression tests for issue #120: no model defined clone_fields, so every
Clone button opened an essentially empty create form.
"""

import datetime

import pytest
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, DirectBuried, Structure

SRID = get_srid()


@pytest.fixture
def endpoints(db):
    s1 = Structure.objects.create(name="CF-S1", geometry=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="CF-S2", geometry=Point(100, 100, srid=SRID))
    return s1, s2


@pytest.fixture
def tenant(db):
    return Tenant.objects.create(name="CF Tenant", slug="cf-tenant")


@pytest.fixture
def installer(db):
    return Tenant.objects.create(name="CF Installer", slug="cf-installer")


@pytest.mark.django_db
class TestAerialSpanClone:
    def test_clone_carries_base_and_span_attributes(self, endpoints, tenant, installer):
        s1, s2 = endpoints
        span = AerialSpan(
            label="CF-AS1",
            status="active",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
            tenant=tenant,
            installed_by=installer,
            installation_date=datetime.date(2025, 6, 1),
            commissioned_date=datetime.date(2025, 7, 1),
            aerial_type="lashed",
            start_attachment_height=6.5,
            end_attachment_height=6.0,
            sag=0.4,
            messenger_size="6M",
            wind_loading="B",
            ice_loading="medium",
        )
        span.save()
        attrs = span.clone()
        assert attrs["status"] == "active"
        assert attrs["start_structure"] == s1.pk
        assert attrs["end_structure"] == s2.pk
        assert attrs["tenant"] == tenant.pk
        assert attrs["installed_by"] == installer.pk
        assert attrs["installation_date"] == datetime.date(2025, 6, 1)
        assert attrs["commissioned_date"] == datetime.date(2025, 7, 1)
        assert attrs["aerial_type"] == "lashed"
        assert attrs["start_attachment_height"] == 6.5
        assert attrs["end_attachment_height"] == 6.0
        assert attrs["sag"] == 0.4
        assert attrs["messenger_size"] == "6M"
        assert attrs["wind_loading"] == "B"
        assert attrs["ice_loading"] == "medium"

    def test_clone_never_carries_identity_or_geometry(self, endpoints):
        s1, s2 = endpoints
        span = AerialSpan(
            label="CF-AS2",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        span.save()
        attrs = span.clone()
        assert "label" not in attrs
        assert "path" not in attrs
        assert "length" not in attrs


@pytest.mark.django_db
class TestDirectBuriedClone:
    def test_clone_carries_burial_attributes(self, endpoints):
        s1, s2 = endpoints
        run = DirectBuried(
            label="CF-DB1",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
            burial_depth=1.2,
            warning_tape=True,
            armor_type="interlocked steel",
        )
        run.save()
        attrs = run.clone()
        assert attrs["burial_depth"] == 1.2
        assert attrs["warning_tape"] is True
        assert attrs["armor_type"] == "interlocked steel"
        assert attrs["start_structure"] == s1.pk
        assert "label" not in attrs
        assert "path" not in attrs
