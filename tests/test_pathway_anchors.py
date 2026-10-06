"""Stored pathway anchors: start_anchor / end_anchor follow attachment.resolve_anchor()."""

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString

from netbox_pathways.models import Conduit, ConduitBank, DirectBuried, SiteGeometry
from tests.helpers import SRID, make_building, make_conduit, make_pole


@pytest.fixture
def building_site(db):
    site = Site.objects.create(name="Building A", slug="building-a")
    building = make_building("B", 0, 0, size=50)
    SiteGeometry.objects.create(site=site, structure=building)
    room = Location.objects.create(name="Room 101", slug="room-101", site=site)
    office = Location.objects.create(name="Office", slug="office", site=site)
    return building, room, office


def test_save_stores_direct_structure_anchors(db):
    s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
    conduit = make_conduit([(0, 0), (100, 0)], start_structure=s1, end_structure=s2)
    assert (conduit.start_anchor, conduit.end_anchor) == (s1, s2)


def test_save_stores_the_structure_enclosing_a_location_end(building_site):
    building, room, _office = building_site
    far = make_pole("P9", 200, 25)
    conduit = make_conduit([(50, 25), (200, 25)], start_location=room, end_structure=far)
    assert (conduit.start_anchor, conduit.end_anchor) == (building, far)


def test_indoor_pathway_gets_anchors_and_still_needs_no_path(building_site):
    building, room, office = building_site
    tray = DirectBuried(start_location=room, end_location=office)
    tray.full_clean()
    tray.save()
    assert tray.path is None
    assert (tray.start_anchor, tray.end_anchor) == (building, building)


def test_bank_conduit_anchors_follow_the_inherited_bank_endpoints(db):
    s1, s2 = make_pole("S1", 0, 0), make_pole("S2", 100, 0)
    bank = ConduitBank(path=LineString((0, 0), (100, 0), srid=SRID), start_structure=s1, end_structure=s2)
    bank.save()
    conduit = Conduit(label="C1", conduit_bank=bank)
    conduit.save()
    assert (conduit.start_anchor, conduit.end_anchor) == (s1, s2)


@pytest.mark.django_db(transaction=True)
def test_backfill_migration_computes_anchors_for_existing_rows(migrate_to):
    pre = "0024_pathway_location_endpoints_protect"
    executor = migrate_to(pre)
    # Only the pathway row needs the pre-anchor schema; dcim is at head in the
    # database, so sites, locations and structures use the live models.
    OldConduit = executor.loader.project_state([("netbox_pathways", pre)]).apps.get_model("netbox_pathways", "Conduit")
    site = Site.objects.create(name="Mig Site", slug="mig-site")
    floor = Location.objects.create(name="Floor", slug="floor", site=site)
    room = Location.objects.create(name="Room", slug="room", site=site, parent=floor)
    building = make_building("Mig B", 0, 0)
    SiteGeometry.objects.create(site=site, structure=building)
    pole = make_pole("Mig P", 100, 0)
    row = OldConduit.objects.create(
        pathway_type="conduit",
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_location_id=room.pk,
        end_structure_id=pole.pk,
    )
    # A shelf under a vault row that IS a structure: the walk stops at the vault.
    vault_row = Location.objects.create(name="Vault Row", slug="vault-row", site=site)
    shelf = Location.objects.create(name="Shelf", slug="shelf", site=site, parent=vault_row)
    vault = make_pole("Mig V", 10, 10)
    vault.location = vault_row
    vault.save()
    shelf_row = OldConduit.objects.create(
        pathway_type="conduit",
        path=LineString((10, 10), (100, 0), srid=SRID),
        start_location_id=shelf.pk,
        end_structure_id=pole.pk,
    )

    executor = migrate_to("0026_backfill_pathway_anchors")
    NewConduit = executor.loader.project_state([("netbox_pathways", "0026_backfill_pathway_anchors")]).apps.get_model(
        "netbox_pathways", "Conduit"
    )
    migrated = NewConduit.objects.get(pk=row.pk)
    assert (migrated.start_anchor_id, migrated.end_anchor_id) == (building.pk, pole.pk)
    assert NewConduit.objects.get(pk=shelf_row.pk).start_anchor_id == vault.pk
