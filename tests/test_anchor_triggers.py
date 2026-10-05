"""Stored anchors follow changes to the site/location hierarchy."""

import pytest
from dcim.models import Location, Site

from netbox_pathways.models import Pathway, SiteGeometry
from tests.helpers import make_building, make_conduit, make_pole


@pytest.fixture
def plant(db):
    """Building B represents site A; Room 101 sits under Floor 1; conduit C runs Room 101 -> P9."""
    site = Site.objects.create(name="Building A", slug="building-a")
    building = make_building("B", 0, 0, size=50)
    site_geometry = SiteGeometry.objects.create(site=site, structure=building)
    floor = Location.objects.create(name="Floor 1", slug="floor-1", site=site)
    room = Location.objects.create(name="Room 101", slug="room-101", site=site, parent=floor)
    far = make_pole("P9", 200, 25)
    conduit = make_conduit([(50, 25), (200, 25)], start_location=room, end_structure=far)
    return {"site": site, "B": building, "site_geometry": site_geometry, "floor": floor, "room": room, "C": conduit}


def _start_anchor(conduit):
    return Pathway.objects.get(pk=conduit.pk).start_anchor


def test_linking_a_structure_to_an_ancestor_location_reanchors_the_subtree(plant):
    riser = make_pole("Riser", 5, 5)
    riser.location = plant["floor"]
    riser.save()

    assert _start_anchor(plant["C"]) == riser


def test_unlinking_a_structure_from_its_location_falls_back_to_the_site(plant):
    riser = make_pole("Riser", 5, 5)
    riser.location = plant["floor"]
    riser.save()

    riser.location = None
    riser.save()

    assert _start_anchor(plant["C"]) == plant["B"]


def test_deleting_the_anchor_structure_falls_back_up_the_walk(plant):
    riser = make_pole("Riser", 5, 5)
    riser.location = plant["floor"]
    riser.save()

    riser.delete()

    assert _start_anchor(plant["C"]) == plant["B"]


def test_unlinking_the_site_structure_leaves_room_ends_unattached(plant):
    plant["site_geometry"].structure = None
    plant["site_geometry"].save()

    assert _start_anchor(plant["C"]) is None


def test_deleting_the_site_geometry_leaves_room_ends_unattached(plant):
    plant["site_geometry"].delete()

    assert _start_anchor(plant["C"]) is None


def test_reparenting_a_location_switches_its_subtree_anchor(plant):
    vault_row = Location.objects.create(name="Vault Row A", slug="vault-row-a", site=plant["site"])
    vault = make_pole("V1", 10, 10)
    vault.location = vault_row
    vault.save()

    plant["floor"].parent = vault_row
    plant["floor"].save()

    assert _start_anchor(plant["C"]) == vault
