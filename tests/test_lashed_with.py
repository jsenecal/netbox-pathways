"""Tests for pathways#9: CableSegment.lashed_with (symmetric self-M2M).

Tracks aerial overlashing -- segments that share the same lash wire on a single
aerial span. The relationship is symmetric: if segment A is lashed with B,
B is automatically lashed with A.
"""

import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import AerialSpan, CableSegment, Structure

SRID = get_srid()


@pytest.fixture
def disable_routability_signal():
    """The routability signal requires both A/B terminations; bypass for these tests."""
    from django.db.models.signals import pre_save

    from netbox_pathways.signals import enforce_cable_routability

    pre_save.disconnect(enforce_cable_routability, sender=CableSegment)
    yield
    pre_save.connect(enforce_cable_routability, sender=CableSegment)


@pytest.fixture
def aerial_route(db):
    s1 = Structure.objects.create(name="LASH-S1", location=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="LASH-S2", location=Point(100, 0, srid=SRID))
    span = AerialSpan(
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=s1,
        end_structure=s2,
    )
    span.pathway_type = "aerial"
    span.save()
    return span


@pytest.mark.django_db
class TestLashedWith:
    def test_pair_is_symmetric(self, aerial_route, disable_routability_signal):
        """Adding seg_b to seg_a.lashed_with auto-adds seg_a to seg_b.lashed_with."""
        cable_a = Cable.objects.create()
        cable_b = Cable.objects.create()
        seg_a = CableSegment.objects.create(cable=cable_a, pathway=aerial_route)
        seg_b = CableSegment.objects.create(cable=cable_b, pathway=aerial_route)
        seg_a.lashed_with.add(seg_b)
        # Symmetric: refetch and check both sides.
        seg_a.refresh_from_db()
        seg_b.refresh_from_db()
        assert seg_b in seg_a.lashed_with.all()
        assert seg_a in seg_b.lashed_with.all()

    def test_remove_is_symmetric(self, aerial_route, disable_routability_signal):
        """Removing the peer from one side removes the reverse too."""
        cable_a = Cable.objects.create()
        cable_b = Cable.objects.create()
        seg_a = CableSegment.objects.create(cable=cable_a, pathway=aerial_route)
        seg_b = CableSegment.objects.create(cable=cable_b, pathway=aerial_route)
        seg_a.lashed_with.add(seg_b)
        seg_a.lashed_with.remove(seg_b)
        seg_a.refresh_from_db()
        seg_b.refresh_from_db()
        assert seg_b not in seg_a.lashed_with.all()
        assert seg_a not in seg_b.lashed_with.all()

    def test_lashed_cables_property(self, aerial_route, disable_routability_signal):
        """The `lashed_cables` property returns the dcim.Cable instances of every peer segment."""
        cable_a = Cable.objects.create()
        cable_b = Cable.objects.create()
        cable_c = Cable.objects.create()
        seg_a = CableSegment.objects.create(cable=cable_a, pathway=aerial_route)
        seg_b = CableSegment.objects.create(cable=cable_b, pathway=aerial_route)
        seg_c = CableSegment.objects.create(cable=cable_c, pathway=aerial_route)
        seg_a.lashed_with.add(seg_b, seg_c)

        cables = list(seg_a.lashed_cables.values_list("pk", flat=True))
        assert sorted(cables) == sorted([cable_b.pk, cable_c.pk])

    def test_segment_delete_clears_peer_links(self, aerial_route, disable_routability_signal):
        """Deleting a segment removes it from every peer's lashed_with set."""
        cable_a = Cable.objects.create()
        cable_b = Cable.objects.create()
        seg_a = CableSegment.objects.create(cable=cable_a, pathway=aerial_route)
        seg_b = CableSegment.objects.create(cable=cable_b, pathway=aerial_route)
        seg_a.lashed_with.add(seg_b)
        seg_a.delete()
        seg_b.refresh_from_db()
        assert seg_b.lashed_with.count() == 0
