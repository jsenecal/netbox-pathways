import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString, Point
from django.core.exceptions import ValidationError

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Structure


@pytest.mark.django_db
class TestCableSegmentSequence:
    @pytest.fixture(autouse=True)
    def _bypass_routability(self, _disable_routability_signal):
        """Sequence tests build orphan segments (no terminations needed)."""

    @pytest.fixture
    def structures(self):
        srid = get_srid()
        return [
            Structure.objects.create(
                name=f"MH-{i}",
                geometry=Point(i, i, srid=srid),
            )
            for i in range(3)
        ]

    @pytest.fixture
    def pathway(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            label="C-1",
            start_structure=structures[0],
            end_structure=structures[1],
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    @pytest.fixture
    def pathway2(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            label="C-2",
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

    def test_explicit_sequence_respected(self, cable, pathway):
        seg = CableSegment(cable=cable, pathway=pathway, sequence=10)
        seg.save()
        assert seg.sequence == 10


@pytest.mark.django_db
class TestCableSegmentRoutability:
    @pytest.fixture
    def structures(self):
        srid = get_srid()
        return [
            Structure.objects.create(
                name=f"MH-RT-{i}",
                geometry=Point(i, i, srid=srid),
            )
            for i in range(2)
        ]

    @pytest.fixture
    def pathway(self, structures):
        srid = get_srid()
        return Conduit.objects.create(
            label="C-RT-1",
            start_structure=structures[0],
            end_structure=structures[1],
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    def test_cable_without_terminations_fails_clean(self, pathway):
        cable = Cable.objects.create(label="NO-TERM-CABLE")
        seg = CableSegment(cable=cable, pathway=pathway)
        with pytest.raises(ValidationError, match="termination"):
            seg.clean()

    def test_cable_without_terminations_fails_save(self, pathway):
        """Pre-save signal also blocks saving."""
        cable = Cable.objects.create(label="NO-TERM-CABLE-2")
        seg = CableSegment(cable=cable, pathway=pathway, sequence=1)
        with pytest.raises(ValidationError, match="termination"):
            seg.save()
