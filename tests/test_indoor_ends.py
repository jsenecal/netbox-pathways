"""Indoor ends: an end belonging to a building through a location, drawn inside its footprint.

Such an end is an indoor position, not a building entry: it stays where it
was drawn, and it moves with the building rather than onto its outline.
"""

from io import StringIO

import pytest
from dcim.models import Location, Site
from django.contrib.gis.geos import LineString
from django.core.management import call_command

from netbox_pathways.models import DirectBuried, SiteGeometry
from tests.helpers import SRID, coords, make_building, square


@pytest.fixture
def building(db):
    """Building B (0..50 square) represents site A, which has Room 101 and Room 102."""
    site = Site.objects.create(name="IE-Site", slug="ie-site")
    structure = make_building("IE-B", 0, 0, size=50)
    SiteGeometry.objects.create(site=site, structure=structure)
    room_101 = Location.objects.create(name="Room 101", slug="room-101", site=site)
    room_102 = Location.objects.create(name="Room 102", slug="room-102", site=site)
    return structure, room_101, room_102


def _indoor_tray(room_101, room_102):
    tray = DirectBuried(start_location=room_101, end_location=room_102, path=LineString((10, 10), (40, 30), srid=SRID))
    tray.full_clean()
    tray.save()
    return tray


def test_indoor_ends_stay_where_drawn(building):
    _b, room_101, room_102 = building
    assert coords(_indoor_tray(room_101, room_102)) == [(10.0, 10.0), (40.0, 30.0)]


def test_location_end_just_outside_the_footprint_snaps_onto_the_outline(building):
    _b, room_101, _room_102 = building
    run = DirectBuried(start_location=room_101, path=LineString((50.5, 25), (200, 25), srid=SRID))
    run.full_clean()
    assert coords(run)[0] == (50.0, 25.0)


def test_end_naming_the_building_directly_still_snaps_onto_the_outline(building):
    structure, _room_101, _room_102 = building
    run = DirectBuried(start_structure=structure, path=LineString((10, 25), (200, 25), srid=SRID))
    run.full_clean()
    assert coords(run)[0] == (0.0, 25.0)


def test_moving_the_building_carries_indoor_ends_with_it(building):
    structure, room_101, room_102 = building
    tray = _indoor_tray(room_101, room_102)

    structure.geometry = square(100, 0, size=50)
    structure.save()

    assert coords(tray, refresh=True) == [(110.0, 10.0), (140.0, 30.0)]


def test_repair_leaves_indoor_ends_alone(building):
    _b, room_101, room_102 = building
    tray = _indoor_tray(room_101, room_102)

    call_command("reanchor_pathways", "--apply", stdout=StringIO())

    assert coords(tray, refresh=True) == [(10.0, 10.0), (40.0, 30.0)]
