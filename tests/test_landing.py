"""Tests for the landing geometry helpers (pure GEOS, no database)."""

import pytest
from django.contrib.gis.geos import Point, Polygon

from netbox_pathways.landing import landing_on, reference_point, relocate
from tests.helpers import SRID, square


def _xy(pt):
    return (round(pt.x, 6), round(pt.y, 6))


def test_reference_point_of_area_is_centroid():
    assert _xy(reference_point(square(0, 0))) == (5.0, 5.0)


def test_landing_on_point_ignores_near():
    pole = Point(3, 4, srid=SRID)
    assert _xy(landing_on(pole, Point(100, 100, srid=SRID))) == (3.0, 4.0)


def test_landing_on_area_projects_onto_facing_edge():
    # A point east of the square lands on its east wall at the same height.
    assert _xy(landing_on(square(0, 0), Point(50, 4, srid=SRID))) == (10.0, 4.0)


def test_landing_on_area_with_hole_uses_outer_ring_from_outside():
    shell = ((0, 0), (20, 0), (20, 20), (0, 20), (0, 0))
    hole = ((8, 8), (12, 8), (12, 12), (8, 12), (8, 8))
    courtyard = Polygon(shell, hole, srid=SRID)
    assert _xy(landing_on(courtyard, Point(30, 10, srid=SRID))) == (20.0, 10.0)


def test_relocate_point_structure_follows_the_point():
    old, new = Point(0, 0, srid=SRID), Point(7, 9, srid=SRID)
    assert _xy(relocate(old, new, Point(0, 0, srid=SRID))) == (7.0, 9.0)


def test_relocate_translated_area_keeps_the_same_wall():
    # Landing on the east wall; the building moves 100 m west. Nearest-point
    # projection would jump to the west wall, relative position must not.
    old, new = square(0, 0), square(-100, 0)
    moved = relocate(old, new, Point(10, 4, srid=SRID))
    assert _xy(moved) == (-90.0, 4.0)


@pytest.mark.parametrize("old", [None, Point(5, 5, srid=SRID)])
def test_relocate_without_comparable_old_area_falls_back_to_nearest(old):
    new = square(0, 0)
    assert _xy(relocate(old, new, Point(50, 4, srid=SRID))) == (10.0, 4.0)
