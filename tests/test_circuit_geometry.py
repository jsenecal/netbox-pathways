# tests/test_circuit_geometry.py
import pytest
from circuits.models import Circuit, CircuitType, Provider
from django.contrib.gis.geos import LineString
from django.db import IntegrityError

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
            cid="TEST-001", provider=provider, type=circuit_type,
        )

    @pytest.fixture
    def line(self):
        srid = get_srid()
        return LineString((0, 0), (1, 1), (2, 0), srid=srid)

    def test_create_minimal(self, circuit, line):
        cg = CircuitGeometry.objects.create(circuit=circuit, path=line)
        assert cg.pk is not None
        assert cg.circuit == circuit
        assert cg.path.num_coords == 3

    def test_str_representation(self, circuit, line):
        cg = CircuitGeometry.objects.create(circuit=circuit, path=line)
        assert "TEST-001" in str(cg)

    def test_one_to_one_constraint(self, circuit, line):
        CircuitGeometry.objects.create(circuit=circuit, path=line)
        with pytest.raises(IntegrityError):
            CircuitGeometry.objects.create(circuit=circuit, path=line)

    def test_provider_reference_optional(self, circuit, line):
        cg = CircuitGeometry.objects.create(
            circuit=circuit, path=line, provider_reference="PROV-ROUTE-42",
        )
        assert cg.provider_reference == "PROV-ROUTE-42"

    def test_cascade_delete(self, circuit, line):
        cg = CircuitGeometry.objects.create(circuit=circuit, path=line)
        pk = cg.pk
        circuit.delete()
        assert not CircuitGeometry.objects.filter(pk=pk).exists()
