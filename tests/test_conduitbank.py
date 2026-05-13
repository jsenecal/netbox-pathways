"""Tests for ConduitBank-specific fields beyond the Pathway base.

Currently covers the ``height``/``width`` additions (number of duct rows and
columns) added in migration ``0017_conduitbank_height_width``. These verify
default-null behavior and round-trip assignment -- plugin-owned field
semantics, not framework plumbing.
"""

import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import ConduitBank, Structure

SRID = get_srid()


@pytest.mark.django_db
class TestConduitBankHeightWidth:
    def test_height_and_width_default_to_null(self):
        s1 = Structure.objects.create(
            name="ConduitBank HW test A",
            structure_type="manhole",
            location=Point(0, 0, srid=SRID),
        )
        s2 = Structure.objects.create(
            name="ConduitBank HW test B",
            structure_type="manhole",
            location=Point(100, 0, srid=SRID),
        )
        cb = ConduitBank.objects.create(
            label="HW test bank",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
        )
        cb.refresh_from_db()
        assert cb.height is None
        assert cb.width is None

    def test_height_and_width_accept_integers(self):
        s1 = Structure.objects.create(
            name="ConduitBank HW test C",
            structure_type="manhole",
            location=Point(200, 0, srid=SRID),
        )
        s2 = Structure.objects.create(
            name="ConduitBank HW test D",
            structure_type="manhole",
            location=Point(300, 0, srid=SRID),
        )
        cb = ConduitBank.objects.create(
            label="HW test bank 2",
            path=LineString((200, 0), (300, 0), srid=SRID),
            start_structure=s1,
            end_structure=s2,
            height=4,
            width=4,
        )
        cb.refresh_from_db()
        assert cb.height == 4
        assert cb.width == 4
