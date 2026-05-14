"""Tests for route-planner view helpers."""

import pytest
from django.contrib.gis.geos import Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Structure
from netbox_pathways.views import RoutePlannerFindView, RoutePlannerView

# ---------------------------------------------------------------------------
# RoutePlannerFindView._parse_int_list
# ---------------------------------------------------------------------------


class TestParseIntList:
    def test_none_returns_none(self):
        assert RoutePlannerFindView._parse_int_list(None) is None

    def test_empty_string_returns_none(self):
        assert RoutePlannerFindView._parse_int_list("") is None

    def test_empty_list_returns_none(self):
        assert RoutePlannerFindView._parse_int_list([]) is None

    def test_comma_separated_string(self):
        assert RoutePlannerFindView._parse_int_list("1,2,3") == [1, 2, 3]

    def test_comma_separated_with_whitespace(self):
        assert RoutePlannerFindView._parse_int_list(" 1 , 2 , 3 ") == [1, 2, 3]

    def test_list_of_ints(self):
        assert RoutePlannerFindView._parse_int_list([1, 2, 3]) == [1, 2, 3]

    def test_list_of_strings(self):
        assert RoutePlannerFindView._parse_int_list(["1", "2"]) == [1, 2]

    def test_list_of_comma_separated_strings(self):
        # getlist may return ["1,2", "3"] when multiple form fields share a name
        assert RoutePlannerFindView._parse_int_list(["1,2", "3"]) == [1, 2, 3]

    def test_garbage_in_string_returns_none(self):
        # All-or-nothing on the string path -- mirrors the source's try/except
        assert RoutePlannerFindView._parse_int_list("abc") is None

    def test_garbage_in_list_is_skipped(self):
        # Per-item path tolerates garbage and keeps the valid items
        assert RoutePlannerFindView._parse_int_list(["1", "abc", "2"]) == [1, 2]

    def test_all_garbage_in_list_returns_none(self):
        assert RoutePlannerFindView._parse_int_list(["abc", "def"]) is None


# ---------------------------------------------------------------------------
# RoutePlannerView._resolve_termination
# ---------------------------------------------------------------------------


@pytest.fixture
def view():
    return RoutePlannerView()


def _build_cable_with_terminations(*, label, site, terminate_a=True, terminate_b=True):
    """Build a Cable with optional A-/B-side terminations rooted in `site`.

    Each side is wired to an Interface on a Device in `site`, which causes
    `CableTermination.cache_related_objects()` to populate `_site` from
    `termination.device.site` on save.
    """
    from dcim.models import (
        Cable,
        CableTermination,
        Device,
        DeviceRole,
        DeviceType,
        Interface,
        Manufacturer,
    )
    from django.contrib.contenttypes.models import ContentType

    mfr, _ = Manufacturer.objects.get_or_create(name="RP-mfr", slug="rp-mfr")
    dt, _ = DeviceType.objects.get_or_create(
        manufacturer=mfr,
        model="RP-dt",
        slug="rp-dt",
    )
    dr, _ = DeviceRole.objects.get_or_create(name="RP-dr", slug="rp-dr")

    cable = Cable.objects.create(label=label)
    iface_ct = ContentType.objects.get_for_model(Interface)

    if terminate_a:
        dev_a = Device.objects.create(
            name=f"{label}-devA",
            device_type=dt,
            role=dr,
            site=site,
        )
        iface_a = Interface.objects.create(name="eth0", device=dev_a, type="1000base-t")
        CableTermination.objects.create(
            cable=cable,
            cable_end="A",
            termination_type=iface_ct,
            termination_id=iface_a.pk,
        )
    if terminate_b:
        dev_b = Device.objects.create(
            name=f"{label}-devB",
            device_type=dt,
            role=dr,
            site=site,
        )
        iface_b = Interface.objects.create(name="eth0", device=dev_b, type="1000base-t")
        CableTermination.objects.create(
            cable=cable,
            cable_end="B",
            termination_type=iface_ct,
            termination_id=iface_b.pk,
        )

    return cable


@pytest.mark.django_db
class TestResolveTermination:
    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def site(self):
        from dcim.models import Site

        return Site.objects.create(name="RP-site", slug="rp-site")

    @pytest.fixture
    def structure(self, site, srid):
        return Structure.objects.create(
            name="RP-struct",
            site=site,
            location=Point(0, 0, srid=srid),
        )

    def test_no_termination_returns_none(self, view):
        # Cable exists but has no CableTermination rows on either end
        from dcim.models import Cable

        cable = Cable.objects.create(label="RP-empty")
        assert view._resolve_termination(cable, "A") is None
        assert view._resolve_termination(cable, "B") is None

    def test_a_side_resolves_to_structure(self, view, site, structure):
        cable = _build_cable_with_terminations(label="RP-A", site=site, terminate_a=True, terminate_b=False)
        assert view._resolve_termination(cable, "A") == structure

    def test_b_side_resolves_to_structure(self, view, site, structure):
        cable = _build_cable_with_terminations(label="RP-B", site=site, terminate_a=False, terminate_b=True)
        assert view._resolve_termination(cable, "B") == structure
