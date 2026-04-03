import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString, Point
from django.db import IntegrityError

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Structure


@pytest.mark.django_db
class TestCableSegmentSequence:
    @pytest.fixture
    def structures(self):
        srid = get_srid()
        return [
            Structure.objects.create(
                name=f"MH-{i}",
                location=Point(i, i, srid=srid),
            ) for i in range(3)
        ]

    @pytest.fixture
    def pathway(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            name="C-1",
            start_structure=structures[0],
            end_structure=structures[1],
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    @pytest.fixture
    def pathway2(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            name="C-2",
            start_structure=structures[1],
            end_structure=structures[2],
            path=LineString((1, 1), (2, 2), srid=srid),
        )

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-001")

    def test_auto_sequence_first_segment(self, cable, pathway):
        seg = CableSegment(cable=cable, pathway=pathway)
        seg.save()
        assert seg.sequence == 1

    def test_auto_sequence_increments(self, cable, pathway, pathway2):
        seg1 = CableSegment.objects.create(cable=cable, pathway=pathway)
        seg2 = CableSegment(cable=cable, pathway=pathway2)
        seg2.save()
        assert seg1.sequence == 1
        assert seg2.sequence == 2

    def test_sequence_unique_per_cable(self, cable, pathway, pathway2):
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)
        with pytest.raises(IntegrityError):
            CableSegment.objects.create(cable=cable, pathway=pathway2, sequence=1)

    def test_explicit_sequence_respected(self, cable, pathway):
        seg = CableSegment(cable=cable, pathway=pathway, sequence=10)
        seg.save()
        assert seg.sequence == 10

    def test_no_slack_fields(self):
        """slack_loop_location and slack_length should not exist on model."""
        field_names = [f.name for f in CableSegment._meta.get_fields()]
        assert 'slack_loop_location' not in field_names
        assert 'slack_length' not in field_names
