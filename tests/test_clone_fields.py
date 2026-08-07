"""Clone action pre-fill: per-model clone_fields declarations.

Regression tests for issue #120: no model defined clone_fields, so every
Clone button opened an essentially empty create form.
"""

import datetime

import pytest
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant

from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    AerialSpan,
    Conduit,
    ConduitBank,
    DirectBuried,
    Innerduct,
    Structure,
)

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


@pytest.mark.django_db
class TestConduitBankClone:
    def test_clone_carries_bank_attributes(self, endpoints):
        s1, s2 = endpoints
        bank = ConduitBank(
            label="CF-BANK1",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
            start_face="north",
            end_face="south",
            configuration="2x3",
            total_conduits=6,
            height=600,
            width=900,
            encasement_type="concrete",
        )
        bank.save()
        attrs = bank.clone()
        assert attrs["start_face"] == "north"
        assert attrs["end_face"] == "south"
        assert attrs["configuration"] == "2x3"
        assert attrs["total_conduits"] == 6
        assert attrs["height"] == 600
        assert attrs["width"] == 900
        assert attrs["encasement_type"] == "concrete"
        assert attrs["start_structure"] == s1.pk
        assert "label" not in attrs
        assert "path" not in attrs


@pytest.mark.django_db
class TestConduitClone:
    def test_clone_carries_bank_membership_and_attributes(self, endpoints):
        s1, s2 = endpoints
        bank = ConduitBank(
            label="CF-BANK2",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        bank.save()
        conduit = Conduit(
            label="CF-C1",
            conduit_bank=bank,
            bank_position="A1",
            start_face="east",
            end_face="west",
            material="hdpe",
            inner_diameter=94.0,
            outer_diameter=110.0,
            depth=1.1,
        )
        conduit.save()
        attrs = conduit.clone()
        assert attrs["conduit_bank"] == bank.pk
        assert attrs["start_face"] == "east"
        assert attrs["end_face"] == "west"
        assert attrs["material"] == "hdpe"
        assert attrs["inner_diameter"] == 94.0
        assert attrs["outer_diameter"] == 110.0
        assert attrs["depth"] == 1.1
        assert "bank_position" not in attrs
        assert "label" not in attrs

    def test_junction_endpoints_are_clonable(self):
        assert "start_junction" in Conduit.clone_fields
        assert "end_junction" in Conduit.clone_fields


@pytest.mark.django_db
class TestInnerductClone:
    def test_clone_carries_parent_size_and_color(self, endpoints):
        s1, s2 = endpoints
        parent = Conduit(
            label="CF-C2",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        parent.save()
        duct = Innerduct(
            label="CF-ID1",
            parent_conduit=parent,
            size="32mm",
            color="ff9800",
            position="1",
        )
        duct.save()
        attrs = duct.clone()
        assert attrs["parent_conduit"] == parent.pk
        assert attrs["size"] == "32mm"
        assert attrs["color"] == "ff9800"
        assert "position" not in attrs
        assert "label" not in attrs
