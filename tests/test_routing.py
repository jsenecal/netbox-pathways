import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Structure
from netbox_pathways.routing import validate_cable_route


@pytest.mark.django_db
class TestValidateCableRoute:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def structures(self, srid):
        return [
            Structure.objects.create(
                name=f"MH-R-{i}",
                location=Point(i, i, srid=srid),
            )
            for i in range(4)
        ]

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-R-001")

    def _make_conduit(self, label, s_from, s_to, srid):
        return Conduit.objects.create(
            label=label, start_structure=s_from, end_structure=s_to,
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    def test_no_segments(self, cable):
        result = validate_cable_route(cable.pk)
        assert result['segment_count'] == 0
        assert result['valid'] is False

    def test_single_segment_valid(self, cable, structures, srid):
        pw = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        CableSegment.objects.create(cable=cable, pathway=pw)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is True
        assert result['gaps'] == []

    def test_connected_route_valid(self, cable, structures, srid):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        pw2 = self._make_conduit("C-R-2", structures[1], structures[2], srid)
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=pw2)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is True
        assert result['gaps'] == []

    def test_gap_detected(self, cable, structures, srid):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        pw2 = self._make_conduit("C-R-2", structures[2], structures[3], srid)
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=pw2)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is False
        assert len(result['gaps']) == 1

    def test_segment_with_null_pathway(self, cable, structures, srid):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=None)
        result = validate_cable_route(cable.pk)
        assert result['valid'] is False
        assert len(result['gaps']) == 1
