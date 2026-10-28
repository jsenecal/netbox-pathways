"""A structure page's pathways tab and connected-structures panel."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.geos import LineString
from django.test import RequestFactory
from users.models import ObjectPermission

from netbox_pathways.models import Pathway
from netbox_pathways.views import StructurePathwaysView, StructureView
from tests.helpers import SRID, make_conduit, make_pole


@pytest.fixture
def poles(db):
    return make_pole("SV-S1", 0, 0), make_pole("SV-S2", 100, 0), make_pole("SV-S3", 0, 100)


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


def _pathway(pathway_type, a, b):
    return Pathway.objects.create(
        pathway_type=pathway_type,
        geometry=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=a,
        end_structure=b,
    )


def test_tab_lists_and_counts_every_pathway_at_the_structure(poles, admin_user):
    s1, s2, s3 = poles
    _pathway("conduit_bank", s1, s2)
    _pathway("aerial", s2, s1)
    _pathway("submarine", s2, s3)

    assert (StructurePathwaysView.tab.badge(s1), StructurePathwaysView.tab.badge(s3)) == (2, 1)
    children = StructurePathwaysView().get_children(_request(admin_user), s1)
    assert sorted(children.values_list("pathway_type", flat=True)) == ["aerial", "conduit_bank"]


def test_tab_lists_only_pathways_the_user_may_view(poles):
    """A user allowed to view only aerial spans sees only those on the tab."""
    s1, s2, _ = poles
    _pathway("conduit_bank", s1, s2)
    span = _pathway("aerial", s1, s2)
    user = get_user_model().objects.create_user(username="sv-aerial-only")
    permission = ObjectPermission.objects.create(
        name="sv-aerial-only", actions=["view"], constraints={"pathway_type": "aerial"}
    )
    permission.object_types.add(ContentType.objects.get_for_model(Pathway))
    permission.users.add(user)

    assert list(StructurePathwaysView().get_children(_request(user), s1)) == [span]


def test_connected_structures_panel_lists_far_ends(poles):
    s1, s2, s3 = poles
    make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
    make_conduit([(0, 100), (0, 0)], start_structure=s3, end_structure=s1)

    table = StructureView().get_extra_context(None, s1)["connected_structures_table"]

    assert set(table.data.data) == {s2, s3}
