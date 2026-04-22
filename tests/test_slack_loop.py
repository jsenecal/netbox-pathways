import pytest
from dcim.models import Cable
from django.contrib.gis.geos import Point
from django.db import IntegrityError

from netbox_pathways.geo import get_srid
from netbox_pathways.models import SlackLoop, Structure


@pytest.mark.django_db
class TestSlackLoop:
    @pytest.fixture
    def structure(self):
        srid = get_srid()
        return Structure.objects.create(name="MH-SL-1", location=Point(0, 0, srid=srid))

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-SL-001")

    def test_create_underground_slack(self, cable, structure):
        sl = SlackLoop.objects.create(
            cable=cable, structure=structure, length=3.5,
        )
        assert sl.pk is not None
        assert sl.pathway is None
        assert sl.length == 3.5

    def test_structure_required(self, cable):
        with pytest.raises(IntegrityError):
            SlackLoop.objects.create(cable=cable, structure=None, length=1.0)

    def test_str_representation(self, cable, structure):
        sl = SlackLoop.objects.create(
            cable=cable, structure=structure, length=5.0,
        )
        assert cable.label in str(sl)
        assert structure.name in str(sl)

    def test_multiple_per_cable_structure(self, cable, structure):
        """Multiple slack loops at the same structure are valid."""
        sl1 = SlackLoop.objects.create(cable=cable, structure=structure, length=3.0)
        sl2 = SlackLoop.objects.create(cable=cable, structure=structure, length=2.0)
        assert sl1.pk != sl2.pk
