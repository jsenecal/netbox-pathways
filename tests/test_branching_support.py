"""Tests for the netbox-branching support shipped with the plugin (#103).

netbox-branching itself is not installed in the test environment, so the
resolver is exercised directly and the map extent is checked for routing
through the database router rather than through a live branch.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from netbox_pathways.branching import lashed_with_resolver, register_branching_resolvers
from netbox_pathways.models import CableSegment, Structure
from netbox_pathways.views import MapView

from .helpers import make_pole


def test_lashed_with_resolver_claims_only_the_through_table():
    """The auto-created lashed_with M2M table is branchable; other models are left to branching."""
    assert lashed_with_resolver(CableSegment.lashed_with.through) is True
    assert lashed_with_resolver(Structure) is None


def test_register_branching_resolvers_registers_when_branching_is_installed():
    """With netbox-branching importable the resolver is handed to it; without it nothing happens."""
    utilities = MagicMock()
    fake_modules = {"netbox_branching": MagicMock(utilities=utilities), "netbox_branching.utilities": utilities}
    with patch.dict(sys.modules, fake_modules):
        register_branching_resolvers()
    utilities.register_branching_resolver.assert_called_once_with(lashed_with_resolver)

    with patch.dict(sys.modules, {"netbox_branching": None, "netbox_branching.utilities": None}):
        register_branching_resolvers()


@pytest.mark.django_db
def test_data_extent_reads_through_the_router():
    """A branch-only structure counts: the extent query uses the connection the router picks."""
    make_pole("BR-extent", 1000, 2000)

    with patch("django.db.router.db_for_read", return_value="default") as db_for_read:
        extent = MapView()._data_extent()

    db_for_read.assert_any_call(Structure)
    assert extent is not None
    west, south, east, north = extent
    assert west == pytest.approx(east)
    assert south == pytest.approx(north)
