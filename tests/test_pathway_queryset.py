"""PathwayQuerySet.touching: which pathways have an end attached to a structure."""

import pytest
from dcim.models import Location, Site

from netbox_pathways.models import Conduit, Pathway
from tests.helpers import make_conduit, make_pole


@pytest.fixture
def plant(db):
    """A vault that is also a dcim.Location, a direct conduit and a location-attached one."""
    site = Site.objects.create(name="PQ-Site", slug="pq-site")
    loc = Location.objects.create(name="PQ-Loc", slug="pq-loc", site=site)
    vault = make_pole("PQ-Vault", 0, 0)
    vault.location = loc
    vault.save()
    far = make_pole("PQ-Far", 100, 0)
    direct = make_conduit([(0, 0), (100, 0)], start_structure=vault, end_structure=far)
    via_location = make_conduit([(0, 0), (100, 0)], start_location=loc, end_structure=far)
    return vault, direct, via_location


def test_touching_counts_direct_ends_only_by_default(plant):
    vault, direct, _via_location = plant
    assert set(Pathway.objects.touching(vault)) == {Pathway.objects.get(pk=direct.pk)}


def test_touching_via_location_adds_identity_location_ends(plant):
    vault, direct, via_location = plant
    assert set(Conduit.objects.touching(vault, via_location=True)) == {direct, via_location}
