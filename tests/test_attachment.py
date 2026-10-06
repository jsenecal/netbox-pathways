"""resolve_anchor: the structure a pathway end attaches to.

Fixture plant (the example used in docs/user-guide/attachment.md):

    Site "Building A"   -- SiteGeometry.structure --> B (building outline)
     |- Floor 1
     |   '- Room 101
     '- Vault Row A     <-- Structure.location --  V1
         '- Shelf 3
"""

import pytest
from dcim.models import Location, Site

from netbox_pathways.attachment import resolve_anchor
from netbox_pathways.models import SiteGeometry
from tests.helpers import make_building, make_pole


@pytest.fixture
def plant(db):
    site = Site.objects.create(name="Building A", slug="building-a")
    building = make_building("B", 0, 0, size=50)
    SiteGeometry.objects.create(site=site, structure=building)
    floor = Location.objects.create(name="Floor 1", slug="floor-1", site=site)
    room = Location.objects.create(name="Room 101", slug="room-101", site=site, parent=floor)
    vault_row = Location.objects.create(name="Vault Row A", slug="vault-row-a", site=site)
    shelf = Location.objects.create(name="Shelf 3", slug="shelf-3", site=site, parent=vault_row)
    vault = make_pole("V1", 10, 10)
    vault.location = vault_row
    vault.save()
    return {"site": site, "B": building, "room": room, "vault_row": vault_row, "shelf": shelf, "V1": vault}


def test_direct_structure_wins(plant):
    pole = make_pole("P9", 200, 0)
    assert resolve_anchor(pole, plant["room"]) == pole


def test_location_with_its_own_structure_attaches_to_it(plant):
    assert resolve_anchor(None, plant["vault_row"]) == plant["V1"]


def test_child_location_attaches_to_nearest_ancestor_structure(plant):
    assert resolve_anchor(None, plant["shelf"]) == plant["V1"]


def test_location_without_structure_above_it_attaches_to_the_site_structure(plant):
    assert resolve_anchor(None, plant["room"]) == plant["B"]


def test_location_in_a_site_without_structure_is_unattached(db):
    site = Site.objects.create(name="Bare", slug="bare")
    loc = Location.objects.create(name="Closet", slug="closet", site=site)
    assert resolve_anchor(None, loc) is None


def test_no_endpoint_is_unattached(db):
    assert resolve_anchor(None, None) is None
