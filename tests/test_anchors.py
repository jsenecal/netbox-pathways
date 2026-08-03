"""Tests for anchor resolution -- where a cable's ends sit in the plant.

Issue #106: the Route tab resolved a cable end to a single Structure guessed
from the termination's site, so structures without a site, sites with several
structures, and every location-terminated pathway produced an empty dropdown.
"""

import pytest
from django.contrib.gis.geos import Point

from netbox_pathways.anchors import REASON_MESSAGES, cable_end_nodes, describe
from netbox_pathways.geo import get_srid
from netbox_pathways.models import SiteGeometry, Structure
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="AN-site", slug="an-site")


@pytest.fixture
def building(site):
    from dcim.models import Location

    return Location.objects.create(name="AN-building", slug="an-building", site=site)


@pytest.fixture
def room(site, building):
    from dcim.models import Location

    return Location.objects.create(name="AN-room", slug="an-room", site=site, parent=building)


@pytest.mark.django_db
class TestCableEndNodes:
    def test_location_and_its_ancestors_are_candidates(self, site, building, room):
        cable = build_cable_with_terminations(label="AN-loc", site=site, location=room)
        anchor = cable_end_nodes(cable, "A")
        assert ("location", room.pk) in anchor.nodes
        assert ("location", building.pk) in anchor.nodes
        # Deepest first: the room outranks the building it sits in.
        assert anchor.nodes.index(("location", room.pk)) < anchor.nodes.index(("location", building.pk))

    def test_site_geometry_structure_is_a_candidate(self, site):
        structure = Structure.objects.create(name="AN-sg", geometry=Point(0, 0, srid=SRID))
        SiteGeometry.objects.create(site=site, structure=structure)
        cable = build_cable_with_terminations(label="AN-sg-cable", site=site)
        assert ("structure", structure.pk) in cable_end_nodes(cable, "A").nodes

    def test_every_structure_in_the_site_is_a_candidate(self, site):
        first = Structure.objects.create(name="AN-a", site=site, geometry=Point(0, 0, srid=SRID))
        second = Structure.objects.create(name="AN-b", site=site, geometry=Point(1, 1, srid=SRID))
        cable = build_cable_with_terminations(label="AN-multi", site=site)
        nodes = cable_end_nodes(cable, "A").nodes
        # Both, not just the alphabetically first -- this is the #106 regression.
        assert ("structure", first.pk) in nodes
        assert ("structure", second.pk) in nodes

    def test_structures_at_the_location_outrank_other_site_structures(self, site, room):
        elsewhere = Structure.objects.create(name="AN-aaa-elsewhere", site=site, geometry=Point(0, 0, srid=SRID))
        at_room = Structure.objects.create(
            name="AN-zzz-at-room",
            site=site,
            location=room,
            geometry=Point(1, 1, srid=SRID),
        )
        cable = build_cable_with_terminations(label="AN-order", site=site, location=room)
        nodes = cable_end_nodes(cable, "A").nodes
        assert nodes.index(("structure", at_room.pk)) < nodes.index(("structure", elsewhere.pk))

    def test_candidates_are_deduplicated(self, site, room):
        structure = Structure.objects.create(
            name="AN-dup",
            site=site,
            location=room,
            geometry=Point(0, 0, srid=SRID),
        )
        SiteGeometry.objects.create(site=site, structure=structure)
        cable = build_cable_with_terminations(label="AN-dup-cable", site=site, location=room)
        nodes = cable_end_nodes(cable, "A").nodes
        assert nodes.count(("structure", structure.pk)) == 1

    def test_labels_line_up_with_nodes(self, site, room):
        Structure.objects.create(name="AN-labelled", site=site, geometry=Point(0, 0, srid=SRID))
        cable = build_cable_with_terminations(label="AN-labels", site=site, location=room)
        anchor = cable_end_nodes(cable, "A")
        assert len(anchor.labels) == len(anchor.nodes)
        assert "AN-labelled" in anchor.labels

    def test_structures_property_returns_structure_pks_in_order(self, site):
        first = Structure.objects.create(name="AN-s1", site=site, geometry=Point(0, 0, srid=SRID))
        second = Structure.objects.create(name="AN-s2", site=site, geometry=Point(1, 1, srid=SRID))
        cable = build_cable_with_terminations(label="AN-props", site=site)
        assert cable_end_nodes(cable, "A").structures == (first.pk, second.pk)

    def test_nothing_in_plant_when_pathways_knows_the_site_not_at_all(self, site):
        cable = build_cable_with_terminations(label="AN-empty", site=site)
        anchor = cable_end_nodes(cable, "A")
        assert anchor.nodes == ()
        assert anchor.is_resolved is False
        assert anchor.unresolved_reason == "nothing_in_plant"
        assert anchor.site == site

    def test_termination_not_sited_when_no_site_and_no_location(self, site):
        from dcim.models import CableTermination

        cable = build_cable_with_terminations(label="AN-unsited", site=site)
        # A circuit termination bound to a provider network looks exactly like
        # this: both cached ancestry fields null.
        CableTermination.objects.filter(cable=cable, cable_end="A").update(_site=None, _location=None)
        anchor = cable_end_nodes(cable, "A")
        assert anchor.unresolved_reason == "termination_not_sited"

    def test_b_end_resolves_independently(self, site):
        structure = Structure.objects.create(name="AN-bend", site=site, geometry=Point(0, 0, srid=SRID))
        cable = build_cable_with_terminations(label="AN-bend-cable", site=site)
        assert ("structure", structure.pk) in cable_end_nodes(cable, "B").nodes


@pytest.mark.django_db
class TestDescribe:
    def test_resolved_end_describes_its_labels(self, site):
        Structure.objects.create(name="AN-desc", site=site, geometry=Point(0, 0, srid=SRID))
        cable = build_cable_with_terminations(label="AN-desc-cable", site=site)
        described = describe(cable_end_nodes(cable, "A"), "A")
        assert described["labels"] == ["AN-desc"]
        assert described["message"] is None

    def test_unresolved_end_describes_message_and_remedy(self, site):
        cable = build_cable_with_terminations(label="AN-desc-empty", site=site)
        described = describe(cable_end_nodes(cable, "A"), "A")
        assert described["labels"] == []
        assert site.name in described["message"]
        assert described["remedy"] == REASON_MESSAGES["nothing_in_plant"][1]
