"""Derived tenancy: own tenant wins; blank falls back up the parent chain.

Mirrors NetBox core's VRF/prefix display fallback. Regression tests for
issue #77.
"""

import pytest
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, ConduitBank, Innerduct, Structure

SRID = get_srid()


@pytest.fixture
def tenants(db):
    owner = Tenant.objects.create(name="Owner Co", slug="owner-co")
    override = Tenant.objects.create(name="Override Co", slug="override-co")
    return owner, override


@pytest.fixture
def bank(db, tenants):
    owner, _ = tenants
    s1 = Structure.objects.create(name="ET-S1", geometry=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="ET-S2", geometry=Point(100, 100, srid=SRID))
    bank = ConduitBank(
        label="ET-BANK",
        path=LineString((0, 0), (100, 100), srid=SRID),
        start_structure=s1,
        end_structure=s2,
        tenant=owner,
    )
    bank.save()
    return bank


@pytest.mark.django_db
class TestEffectiveTenant:
    def test_conduit_own_tenant_wins(self, bank, tenants):
        _, override = tenants
        conduit = Conduit(label="ET-C1", conduit_bank=bank, tenant=override)
        conduit.save()
        assert conduit.effective_tenant == override

    def test_conduit_falls_back_to_bank(self, bank, tenants):
        owner, _ = tenants
        conduit = Conduit(label="ET-C2", conduit_bank=bank)
        conduit.save()
        assert conduit.tenant is None
        assert conduit.effective_tenant == owner

    def test_standalone_conduit_without_tenant_is_none(self, db):
        s1 = Structure.objects.create(name="ET-S3", geometry=Point(0, 0, srid=SRID))
        s2 = Structure.objects.create(name="ET-S4", geometry=Point(1, 1, srid=SRID))
        conduit = Conduit(
            label="ET-C3",
            path=LineString((0, 0), (1, 1), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        conduit.save()
        assert conduit.effective_tenant is None

    def test_innerduct_chains_to_bank(self, bank, tenants):
        owner, _ = tenants
        conduit = Conduit(label="ET-C4", conduit_bank=bank)
        conduit.save()
        duct = Innerduct(label="ET-I1", parent_conduit=conduit, size="32mm")
        duct.save()
        assert duct.effective_tenant == owner

    def test_innerduct_own_tenant_wins(self, bank, tenants):
        _, override = tenants
        conduit = Conduit(label="ET-C5", conduit_bank=bank)
        conduit.save()
        duct = Innerduct(label="ET-I2", parent_conduit=conduit, size="32mm", tenant=override)
        duct.save()
        assert duct.effective_tenant == override
