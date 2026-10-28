"""The single pathway REST endpoint."""

import pytest
from django.urls import NoReverseMatch, reverse
from rest_framework.test import APIClient

from netbox_pathways.models import Pathway
from tests.helpers import make_aerial_span, make_conduit, make_pole

PATHWAY_LIST = "plugins-api:netbox_pathways-api:pathway-list"


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


def test_api_rejects_disallowed_parent(api_client):
    """Containment is enforced through the model rules, keyed on ``parent``."""
    span = make_aerial_span(make_pole("API-P1", 0, 0), make_pole("API-P2", 100, 0))

    response = api_client.post(
        reverse(PATHWAY_LIST),
        {"pathway_type": "innerduct", "label": "ID-1", "parent": span.pk},
        format="json",
    )

    assert response.status_code == 400, response.data
    assert "cannot be inside" in str(response.data["parent"])
    assert not Pathway.objects.filter(label="ID-1").exists()


def test_api_writes_parent_and_nests_it_on_read(api_client):
    conduit = make_conduit([(0, 0), (100, 0)], start_structure=make_pole("API-P3", 0, 0))

    response = api_client.post(
        reverse(PATHWAY_LIST),
        {"pathway_type": "innerduct", "label": "ID-2", "parent": conduit.pk, "size": "32mm"},
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["parent"]["id"] == conduit.pk
    assert response.data["parent"]["pathway_type"]["value"] == "conduit"
    assert Pathway.objects.get(label="ID-2").parent_id == conduit.pk


@pytest.mark.parametrize("basename", ["conduitbank", "conduit", "aerialspan", "directburied", "innerduct"])
def test_api_removed_subtype_endpoints(basename):
    """The per-type REST endpoints are gone, with no aliases."""
    with pytest.raises(NoReverseMatch):
        reverse(f"plugins-api:netbox_pathways-api:{basename}-list")
