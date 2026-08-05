"""Tests for CableTraceView -- param validation and response assembly."""

import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString, Point
from rest_framework.test import APIClient

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Structure

SRID = get_srid()

URL = "/api/plugins/pathways/traversal/cable-trace/"


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.mark.django_db
class TestCableTraceView:
    def test_missing_cable_id_returns_400(self, api_client):
        resp = api_client.get(URL)
        assert resp.status_code == 400
        assert "cable_id" in resp.json()["error"]

    def test_non_integer_cable_id_returns_400(self, api_client):
        resp = api_client.get(f"{URL}?cable_id=abc")
        assert resp.status_code == 400

    def test_trace_sums_lengths_treating_null_as_zero(self, api_client, _disable_routability_signal):
        s = [Structure.objects.create(name=f"TRC-{i}", geometry=Point(i, i, srid=SRID)) for i in range(3)]
        with_length = Conduit.objects.create(
            label="TRC-C1",
            start_structure=s[0],
            end_structure=s[1],
            path=LineString((0, 0), (1, 1), srid=SRID),
            length=10,
        )
        no_length = Conduit.objects.create(
            label="TRC-C2",
            start_structure=s[1],
            end_structure=s[2],
            path=LineString((1, 1), (2, 2), srid=SRID),
        )
        cable = Cable.objects.create(label="TRC-cable")
        CableSegment.objects.create(cable=cable, pathway=with_length, sequence=1)
        CableSegment.objects.create(cable=cable, pathway=no_length, sequence=2)

        resp = api_client.get(f"{URL}?cable_id={cable.pk}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["cable_id"] == cable.pk
        assert data["segment_count"] == 2
        # The second segment has length=None; the sum must not crash on it.
        assert data["total_length"] == 10
