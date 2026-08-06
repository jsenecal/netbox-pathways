"""Create-form prefill from a parent object passed via initial data.

The Add buttons on the parent detail pages link to the child create form
with ?conduit_bank=<pk> / ?parent_conduit=<pk>; the form expands that
single parameter into visible initial values. Regression tests for
issue #77.
"""

import datetime

import pytest
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant

from netbox_pathways.forms import ConduitForm, InnerductForm
from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, ConduitBank, Structure

SRID = get_srid()


@pytest.fixture
def bank(db):
    s1 = Structure.objects.create(name="PF-S1", geometry=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="PF-S2", geometry=Point(100, 100, srid=SRID))
    installer = Tenant.objects.create(name="Installer Inc", slug="installer-inc")
    bank = ConduitBank(
        label="PF-BANK",
        path=LineString((0, 0), (100, 100), srid=SRID),
        start_structure=s1,
        end_structure=s2,
        start_face="north",
        end_face="south",
        installed_by=installer,
        installation_date=datetime.date(2025, 6, 1),
        commissioned_date=datetime.date(2025, 7, 1),
    )
    bank.save()
    return bank


@pytest.mark.django_db
class TestConduitFormPrefill:
    def test_prefills_from_bank_pk(self, bank):
        form = ConduitForm(initial={"conduit_bank": str(bank.pk)})
        assert form.initial["start_structure"] == bank.start_structure.pk
        assert form.initial["end_structure"] == bank.end_structure.pk
        assert form.initial["start_face"] == "north"
        assert form.initial["end_face"] == "south"
        assert form.initial["installed_by"] == bank.installed_by.pk
        assert form.initial["installation_date"] == datetime.date(2025, 6, 1)
        assert form.initial["commissioned_date"] == datetime.date(2025, 7, 1)

    def test_never_prefills_path_or_tenant(self, bank):
        form = ConduitForm(initial={"conduit_bank": str(bank.pk)})
        assert "path" not in form.initial
        assert "tenant" not in form.initial

    def test_explicit_initial_wins(self, bank):
        other = Structure.objects.create(name="PF-S3", geometry=Point(50, 50, srid=SRID))
        form = ConduitForm(initial={"conduit_bank": str(bank.pk), "start_structure": str(other.pk)})
        assert form.initial["start_structure"] == str(other.pk)
        assert form.initial["end_structure"] == bank.end_structure.pk

    def test_bogus_pk_is_ignored(self, db):
        form = ConduitForm(initial={"conduit_bank": "999999"})
        assert "start_structure" not in form.initial
        form = ConduitForm(initial={"conduit_bank": "not-a-pk"})
        assert "start_structure" not in form.initial

    def test_editing_existing_conduit_never_prefills(self, bank):
        conduit = Conduit(label="PF-C1", conduit_bank=bank)
        conduit.save()
        form = ConduitForm(instance=conduit, initial={"conduit_bank": str(bank.pk)})
        assert "start_face" not in form.initial


@pytest.mark.django_db
class TestInnerductFormPrefill:
    def test_prefills_endpoints_only(self, bank):
        parent = Conduit(
            label="PF-C2",
            path=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=bank.start_structure,
            end_structure=bank.end_structure,
            installed_by=bank.installed_by,
            installation_date=datetime.date(2025, 6, 2),
        )
        parent.save()
        form = InnerductForm(initial={"parent_conduit": str(parent.pk)})
        assert form.initial["start_structure"] == parent.start_structure.pk
        assert form.initial["end_structure"] == parent.end_structure.pk
        # lifecycle fields are never inherited by innerducts
        assert "installed_by" not in form.initial
        assert "installation_date" not in form.initial
        assert "commissioned_date" not in form.initial
