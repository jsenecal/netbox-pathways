"""Create-form prefill from a parent object passed via initial data.

The Add buttons on a parent's detail page link to the pathway create form
with ?pathway_type=<type>&parent=<pk>; the form expands that single
parameter into visible initial values. Regression tests for issue #77.
"""

import datetime

import pytest
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant

from netbox_pathways.forms import PathwayForm
from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, Structure

SRID = get_srid()


@pytest.fixture
def bank(db):
    s1 = Structure.objects.create(name="PF-S1", geometry=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="PF-S2", geometry=Point(100, 100, srid=SRID))
    installer = Tenant.objects.create(name="Installer Inc", slug="installer-inc")
    bank = Pathway(
        pathway_type="conduit_bank",
        label="PF-BANK",
        geometry=LineString((0, 0), (100, 100), srid=SRID),
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


def _conduit_form(parent, **initial):
    return PathwayForm(initial={"pathway_type": "conduit", "parent": str(parent), **initial})


@pytest.mark.django_db
class TestConduitFormPrefill:
    def test_prefills_from_bank_pk(self, bank):
        form = _conduit_form(bank.pk)
        assert form.initial["start_structure"] == bank.start_structure.pk
        assert form.initial["end_structure"] == bank.end_structure.pk
        assert form.initial["start_face"] == "north"
        assert form.initial["end_face"] == "south"
        assert form.initial["installed_by"] == bank.installed_by.pk
        assert form.initial["installation_date"] == datetime.date(2025, 6, 1)
        assert form.initial["commissioned_date"] == datetime.date(2025, 7, 1)

    def test_never_prefills_geometry_or_tenant(self, bank):
        form = _conduit_form(bank.pk)
        assert "geometry" not in form.initial
        assert "tenant" not in form.initial

    def test_explicit_initial_wins(self, bank):
        other = Structure.objects.create(name="PF-S3", geometry=Point(50, 50, srid=SRID))
        form = _conduit_form(bank.pk, start_structure=str(other.pk))
        assert form.initial["start_structure"] == str(other.pk)
        assert form.initial["end_structure"] == bank.end_structure.pk

    def test_bogus_pk_is_ignored(self, db):
        assert "start_structure" not in _conduit_form("999999").initial
        assert "start_structure" not in _conduit_form("not-a-pk").initial

    def test_editing_existing_conduit_never_prefills(self, bank):
        conduit = Pathway(pathway_type="conduit", label="PF-C1", parent=bank)
        conduit.save()
        form = PathwayForm(instance=conduit, initial={"parent": str(bank.pk)})
        assert form.initial["start_face"] != bank.start_face
        assert form.initial["end_face"] != bank.end_face


@pytest.mark.django_db
class TestInnerductFormPrefill:
    def test_prefills_endpoints_only(self, bank):
        parent = Pathway(
            pathway_type="conduit",
            label="PF-C2",
            geometry=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=bank.start_structure,
            end_structure=bank.end_structure,
            installed_by=bank.installed_by,
            installation_date=datetime.date(2025, 6, 2),
            position="A1",
        )
        parent.save()
        form = PathwayForm(initial={"pathway_type": "innerduct", "parent": str(parent.pk)})
        assert form.initial["start_structure"] == parent.start_structure.pk
        assert form.initial["end_structure"] == parent.end_structure.pk
        # lifecycle fields are never inherited by innerducts, nor is the
        # parent's own slot
        assert "installed_by" not in form.initial
        assert "installation_date" not in form.initial
        assert "commissioned_date" not in form.initial
        assert "position" not in form.initial

    def test_innerduct_in_direct_buried_prefills_endpoints(self, bank):
        """Any parent prefills, not only the former conduit/bank pairs (#173)."""
        buried = Pathway(
            pathway_type="direct_buried",
            label="PF-DB",
            geometry=LineString((0, 0), (100, 100), srid=SRID),
            start_structure=bank.start_structure,
            end_structure=bank.end_structure,
        )
        buried.save()
        form = PathwayForm(initial={"pathway_type": "innerduct", "parent": str(buried.pk)})
        assert form.initial["start_structure"] == buried.start_structure.pk
        assert form.initial["end_structure"] == buried.end_structure.pk
