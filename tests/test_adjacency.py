import json

import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, Structure


@pytest.mark.django_db
class TestAdjacencyView:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def structures(self, srid):
        return [
            Structure.objects.create(
                name=f"ADJ-{i}", location=Point(i * 0.01, i * 0.01, srid=srid),
            )
            for i in range(3)
        ]

    @pytest.fixture
    def conduits(self, structures, srid):
        return [
            Conduit.objects.create(
                label="C-ADJ-01",
                start_structure=structures[0],
                end_structure=structures[1],
                path=LineString((0, 0), (0.01, 0.01), srid=srid),
                length=10,
            ),
            Conduit.objects.create(
                label="C-ADJ-02",
                start_structure=structures[0],
                end_structure=structures[2],
                path=LineString((0, 0), (0.02, 0.02), srid=srid),
                length=25,
            ),
        ]

    def test_returns_connected_pathways(self, client, structures, conduits, admin_user):
        client.force_login(admin_user)
        url = f"/plugins/pathways/adjacency/?node_type=structure&node_id={structures[0].pk}"
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert len(data) == 2

    def test_returns_empty_for_isolated_node(self, client, srid, admin_user):
        client.force_login(admin_user)
        s = Structure.objects.create(
            name="ISOLATED", location=Point(5, 5, srid=srid),
        )
        url = f"/plugins/pathways/adjacency/?node_type=structure&node_id={s.pk}"
        response = client.get(url)
        assert response.status_code == 200
        data = json.loads(response.content)
        assert len(data) == 0

    def test_missing_params_returns_400(self, client, admin_user):
        client.force_login(admin_user)
        response = client.get("/plugins/pathways/adjacency/")
        assert response.status_code == 400
