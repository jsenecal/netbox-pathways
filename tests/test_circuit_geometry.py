# tests/test_circuit_geometry.py
import pytest
from circuits.models import Circuit, CircuitType, Provider
from django.contrib.gis.geos import LineString

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CircuitGeometry


@pytest.mark.django_db
class TestCircuitGeometry:
    @pytest.fixture
    def provider(self):
        return Provider.objects.create(name="Test Provider", slug="test-provider")

    @pytest.fixture
    def circuit_type(self):
        return CircuitType.objects.create(name="Dark Fiber", slug="dark-fiber")

    @pytest.fixture
    def circuit(self, provider, circuit_type):
        return Circuit.objects.create(
            cid="TEST-001",
            provider=provider,
            type=circuit_type,
        )

    @pytest.fixture
    def line(self):
        srid = get_srid()
        return LineString((0, 0), (1, 1), (2, 0), srid=srid)

    def test_str_representation(self, circuit, line):
        cg = CircuitGeometry.objects.create(circuit=circuit, path=line)
        assert "TEST-001" in str(cg)


def test_rest_serializer_keeps_path_field():
    """CircuitGeometry keeps its ``path`` column through the Pathway rename.

    The Pathway ``path`` -> ``geometry`` rename must not reach the circuit
    serializer: a stale field name makes DRF raise ImproperlyConfigured when
    the fields are built, which 500s every circuit-geometry endpoint.
    """
    from netbox_pathways.api.serializers import CircuitGeometrySerializer

    fields = CircuitGeometrySerializer().fields
    assert "path" in fields
    assert "geometry" not in fields
