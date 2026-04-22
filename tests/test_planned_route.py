import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Conduit, PlannedRoute, Structure


@pytest.mark.django_db
class TestPlannedRoute:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def structures(self, srid):
        return [
            Structure.objects.create(
                name=f"PR-{i}", location=Point(i * 0.01, i * 0.01, srid=srid),
            )
            for i in range(3)
        ]

    @pytest.fixture
    def conduits(self, structures, srid):
        return [
            Conduit.objects.create(
                label=f"C-PR-{i}",
                start_structure=structures[i],
                end_structure=structures[i + 1],
                path=LineString(
                    (i * 0.01, i * 0.01), ((i + 1) * 0.01, (i + 1) * 0.01),
                    srid=srid,
                ),
                length=100,
            )
            for i in range(2)
        ]

    def test_create_planned_route(self, structures, conduits):
        route = PlannedRoute.objects.create(
            name="Test Route",
            start_structure=structures[0],
            end_structure=structures[2],
            pathway_ids=[c.pk for c in conduits],
        )
        assert route.hop_count == 2
        assert route.status == 'draft'
        assert str(route) == "Test Route"

    def test_total_length(self, structures, conduits):
        route = PlannedRoute.objects.create(
            name="Length Test",
            start_structure=structures[0],
            end_structure=structures[2],
            pathway_ids=[c.pk for c in conduits],
        )
        assert route.total_length == 200

    def test_validate_route_all_exist(self, structures, conduits):
        route = PlannedRoute.objects.create(
            name="Valid Route",
            start_structure=structures[0],
            end_structure=structures[2],
            pathway_ids=[c.pk for c in conduits],
        )
        assert route.validate_route() == []

    def test_validate_route_missing_pathway(self, structures, conduits):
        route = PlannedRoute.objects.create(
            name="Stale Route",
            start_structure=structures[0],
            end_structure=structures[2],
            pathway_ids=[conduits[0].pk, 999999],
        )
        assert route.validate_route() == [999999]

    def test_clean_passes_with_structure_endpoints(self, structures):
        route = PlannedRoute(
            name="Good",
            start_structure=structures[0],
            end_structure=structures[1],
            pathway_ids=[],
        )
        route.clean()  # should not raise

    def test_endpoint_properties(self, structures):
        route = PlannedRoute.objects.create(
            name="Props Test",
            start_structure=structures[0],
            end_structure=structures[2],
            pathway_ids=[],
        )
        assert route.start_endpoint == structures[0]
        assert route.end_endpoint == structures[2]
