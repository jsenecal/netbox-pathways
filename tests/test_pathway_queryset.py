"""Which pathways are a structure's: touching(), structure filters, split candidates.

A pathway belongs to a structure when either end's stored anchor is that
structure -- including ends naming a location inside the structure's site.
"""

import pytest
from dcim.models import Cable, Location, Site

from netbox_pathways.filtersets import StructureFilterSet
from netbox_pathways.models import CableSegment, Conduit, Pathway, SiteGeometry, Structure
from netbox_pathways.split import find_candidates
from tests.helpers import make_building, make_conduit, make_pole


@pytest.fixture
def plant(db):
    """Building B represents site A; conduit C runs from Room 101 to pole P9; D runs B -> P9 directly."""
    site = Site.objects.create(name="PQ-Site", slug="pq-site")
    building = make_building("PQ-B", 0, 0, size=50)
    SiteGeometry.objects.create(site=site, structure=building)
    room = Location.objects.create(name="PQ-Room", slug="pq-room", site=site)
    far = make_pole("PQ-P9", 200, 25)
    via_room = make_conduit([(50, 25), (200, 25)], start_location=room, end_structure=far)
    direct = make_conduit([(50, 30), (200, 25)], start_structure=building, end_structure=far)
    return {"B": building, "P9": far, "C": via_room, "D": direct}


def test_touching_includes_ends_anchored_through_a_location(plant):
    assert set(Conduit.objects.touching(plant["B"])) == {plant["C"], plant["D"]}


def test_touching_direct_counts_structure_fields_only(plant):
    assert set(Pathway.objects.touching(plant["B"], direct=True)) == {Pathway.objects.get(pk=plant["D"].pk)}


def test_has_pathways_counts_a_structure_anchored_only_through_a_location(plant):
    plant["D"].delete()
    queryset = StructureFilterSet({"has_pathways": True}, queryset=Structure.objects.all()).qs
    assert plant["B"] in queryset


def test_occupied_counts_a_structure_anchored_only_through_a_location(plant, _disable_routability_signal):
    plant["D"].delete()
    cable = Cable.objects.create(label="PQ-Cable")
    CableSegment.objects.create(cable=cable, pathway=plant["C"], sequence=1)
    queryset = StructureFilterSet({"occupied": True}, queryset=Structure.objects.all()).qs
    assert plant["B"] in queryset


def test_split_candidates_exclude_the_pathway_anchors(plant):
    # C starts on B's outline: B lies on the line but is C's own anchor, not a split point.
    assert plant["B"] not in [candidate.structure for candidate in find_candidates(plant["C"], tolerance=1.0)]
