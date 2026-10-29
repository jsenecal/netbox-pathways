"""Create-form prefill from a parent object passed via initial data.

The Add buttons on a parent's detail page link to the pathway create form
with ?pathway_type=<type>&parent=<pk>; the form expands that single
parameter into visible initial values. Regression tests for issue #77.
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import LineString, Point
from tenancy.models import Tenant
from users.models import ObjectPermission
from utilities.forms.utils import restrict_form_fields

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


def _shown(form, name):
    """The value the rendered form shows for `name` (what BoundField.initial reads)."""
    return form.get_initial_for_field(form.fields[name], name)


def _user_viewing_pathways_labelled(label):
    user_model = get_user_model()
    user = user_model.objects.create_user(username=f"pf-{label}", password="x")  # noqa: S106
    perm = ObjectPermission.objects.create(name=f"pf-{label}", actions=["view"], constraints={"label": label})
    perm.object_types.set([ContentType.objects.get_for_model(Pathway)])
    perm.users.add(user)
    # Re-fetch so no permission cache rides along on the instance.
    return user_model.objects.get(pk=user.pk)


@pytest.mark.django_db
class TestPrefillHonoursViewPermission:
    """The edit view restricts the parent field to viewable pathways only
    after building the form, so the parent is read when the form renders."""

    def test_parent_the_user_cannot_view_prefills_nothing(self, bank):
        form = _conduit_form(bank.pk)
        restrict_form_fields(form, _user_viewing_pathways_labelled("PF-OTHER"))
        for name in ("start_structure", "end_structure", "start_face", "installed_by", "installation_date"):
            assert _shown(form, name) in (None, ""), name

    def test_parent_the_user_can_view_prefills(self, bank):
        form = _conduit_form(bank.pk)
        restrict_form_fields(form, _user_viewing_pathways_labelled(bank.label))
        assert _shown(form, "start_structure") == bank.start_structure.pk
        assert _shown(form, "installation_date") == datetime.date(2025, 6, 1)


@pytest.mark.django_db
class TestConduitFormPrefill:
    def test_prefills_from_bank_pk(self, bank):
        form = _conduit_form(bank.pk)
        assert _shown(form, "start_structure") == bank.start_structure.pk
        assert _shown(form, "end_structure") == bank.end_structure.pk
        assert _shown(form, "start_face") == "north"
        assert _shown(form, "end_face") == "south"
        assert _shown(form, "installed_by") == bank.installed_by.pk
        assert _shown(form, "installation_date") == datetime.date(2025, 6, 1)
        assert _shown(form, "commissioned_date") == datetime.date(2025, 7, 1)

    def test_never_prefills_geometry_or_tenant(self, bank):
        form = _conduit_form(bank.pk)
        assert _shown(form, "geometry") in (None, "")
        assert _shown(form, "tenant") in (None, "")

    def test_explicit_initial_wins(self, bank):
        other = Structure.objects.create(name="PF-S3", geometry=Point(50, 50, srid=SRID))
        form = _conduit_form(bank.pk, start_structure=str(other.pk))
        assert _shown(form, "start_structure") == str(other.pk)
        assert _shown(form, "end_structure") == bank.end_structure.pk

    def test_bogus_pk_is_ignored(self, db):
        assert _shown(_conduit_form("999999"), "start_structure") in (None, "")
        assert _shown(_conduit_form("not-a-pk"), "start_structure") in (None, "")

    def test_editing_existing_conduit_never_prefills(self, bank):
        conduit = Pathway(pathway_type="conduit", label="PF-C1", parent=bank)
        conduit.save()
        form = PathwayForm(instance=conduit, initial={"parent": str(bank.pk)})
        assert _shown(form, "start_face") != bank.start_face
        assert _shown(form, "end_face") != bank.end_face


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
        assert _shown(form, "start_structure") == parent.start_structure.pk
        assert _shown(form, "end_structure") == parent.end_structure.pk
        # lifecycle fields are never inherited by innerducts, nor is the
        # parent's own slot
        assert _shown(form, "installed_by") in (None, "")
        assert _shown(form, "installation_date") in (None, "")
        assert _shown(form, "commissioned_date") in (None, "")
        assert _shown(form, "position") in (None, "")

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
        assert _shown(form, "start_structure") == buried.start_structure.pk
        assert _shown(form, "end_structure") == buried.end_structure.pk
