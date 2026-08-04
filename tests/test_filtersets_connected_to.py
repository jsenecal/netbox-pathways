"""The connected_to filter -- adjacency as a query param.

This is what lets the Route tab picker be a standard DynamicModelChoiceField
instead of a hand-rendered <select> (issue #106), and it replaces the removed
AdjacencyView.
"""

import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.filtersets import PathwayFilterSet
from netbox_pathways.geo import get_srid
from netbox_pathways.models import Pathway, Structure
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def topology(db):
    """A -- P1 -- B, plus P2 hanging off a location."""
    from dcim.models import Location, Site

    site = Site.objects.create(name="CT-site", slug="ct-site")
    location = Location.objects.create(name="CT-loc", slug="ct-loc", site=site)
    a = Structure.objects.create(name="CT-A", geometry=Point(0, 0, srid=SRID))
    b = Structure.objects.create(name="CT-B", geometry=Point(100, 0, srid=SRID))
    p1 = Pathway.objects.create(
        label="CT-P1",
        pathway_type="conduit",
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=a,
        end_structure=b,
    )
    p2 = Pathway.objects.create(
        label="CT-P2",
        pathway_type="conduit",
        path=LineString((100, 0), (200, 0), srid=SRID),
        start_structure=b,
        end_location=location,
    )
    return {"a": a, "b": b, "location": location, "p1": p1, "p2": p2}


def _filter(data):
    return PathwayFilterSet(data, queryset=Pathway.objects.all())


@pytest.mark.django_db
class TestConnectedToFilter:
    def test_structure_node_matches_either_end(self, topology):
        result = _filter({"connected_to": [f"structure:{topology['b'].pk}"]})
        assert set(result.qs.values_list("label", flat=True)) == {"CT-P1", "CT-P2"}

    def test_location_node_matches(self, topology):
        result = _filter({"connected_to": [f"location:{topology['location'].pk}"]})
        assert set(result.qs.values_list("label", flat=True)) == {"CT-P2"}

    def test_several_nodes_are_ored(self, topology):
        result = _filter({"connected_to": [f"structure:{topology['a'].pk}", f"location:{topology['location'].pk}"]})
        assert set(result.qs.values_list("label", flat=True)) == {"CT-P1", "CT-P2"}

    def test_no_duplicate_rows_when_both_ends_match(self, topology):
        result = _filter({"connected_to": [f"structure:{topology['a'].pk}", f"structure:{topology['b'].pk}"]})
        labels = list(result.qs.values_list("label", flat=True))
        assert sorted(labels) == ["CT-P1", "CT-P2"]

    def test_malformed_value_is_a_validation_error(self, topology):
        result = _filter({"connected_to": ["structure-12"]})
        assert result.is_valid() is False
        assert "connected_to" in result.errors

    def test_unknown_kind_is_a_validation_error(self, topology):
        result = _filter({"connected_to": ["planet:12"]})
        assert result.is_valid() is False

    def test_null_is_a_no_op(self, topology):
        """NetBox's APISelect sends `null` for an unset dynamic param."""
        result = _filter({"connected_to": ["null"]})
        assert set(result.qs.values_list("label", flat=True)) == {"CT-P1", "CT-P2"}

    def test_absent_filter_leaves_the_queryset_alone(self, topology):
        assert _filter({}).qs.count() == 2


@pytest.mark.django_db
class TestConnectedToCableEndFilter:
    """`connected_to_cable_end` resolves the anchor server-side.

    The picker cannot send one `connected_to` param per candidate node: a Site
    modeling an exchange area holds hundreds or thousands of structures, and the
    resulting query string overruns nginx's header buffers and Django's
    `DATA_UPLOAD_MAX_NUMBER_FIELDS` -- reported by TomSelect as "no results
    found", which is issue #106 again.
    """

    def test_a_end_resolves_to_the_pathways_at_its_site(self, topology):
        from dcim.models import Site

        site = Site.objects.create(name="CE-site", slug="ce-site")
        anchor = Structure.objects.create(name="CE-anchor", site=site, geometry=Point(0, 0, srid=SRID))
        Pathway.objects.create(
            label="CE-P1",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=anchor,
        )
        cable = build_cable_with_terminations(label="CE-cable", site=site)
        result = _filter({"connected_to_cable_end": [f"{cable.pk}:A"]})
        assert set(result.qs.values_list("label", flat=True)) == {"CE-P1"}

    def test_a_location_terminated_pathway_is_reachable(self, topology):
        """The anchor set spans locations, not just structures."""
        from dcim.models import Location, Site

        site = Site.objects.create(name="CE-loc-site", slug="ce-loc-site")
        room = Location.objects.create(name="CE-room", slug="ce-room", site=site)
        Pathway.objects.create(
            label="CE-indoor",
            pathway_type="conduit",
            path=LineString((0, 0), (50, 0), srid=SRID),
            start_location=room,
        )
        cable = build_cable_with_terminations(label="CE-cable-loc", site=site, location=room)
        result = _filter({"connected_to_cable_end": [f"{cable.pk}:A"]})
        assert set(result.qs.values_list("label", flat=True)) == {"CE-indoor"}

    def test_the_b_end_resolves_independently(self, topology):
        from dcim.models import Site

        site_a = Site.objects.create(name="CE-a", slug="ce-a")
        site_b = Site.objects.create(name="CE-b", slug="ce-b")
        struct_a = Structure.objects.create(name="CE-sa", site=site_a, geometry=Point(0, 0, srid=SRID))
        struct_b = Structure.objects.create(name="CE-sb", site=site_b, geometry=Point(500, 0, srid=SRID))
        Pathway.objects.create(
            label="CE-at-a",
            pathway_type="conduit",
            path=LineString((0, 0), (10, 0), srid=SRID),
            start_structure=struct_a,
        )
        Pathway.objects.create(
            label="CE-at-b",
            pathway_type="conduit",
            path=LineString((500, 0), (510, 0), srid=SRID),
            start_structure=struct_b,
        )
        cable = build_cable_with_terminations(label="CE-cable-ends", site=site_a, site_b=site_b)
        assert set(_filter({"connected_to_cable_end": [f"{cable.pk}:B"]}).qs.values_list("label", flat=True)) == {
            "CE-at-b"
        }

    def test_an_unresolvable_end_matches_nothing(self, topology):
        """The filter was requested; declining to filter is the view's job."""
        from dcim.models import Site

        site = Site.objects.create(name="CE-bare", slug="ce-bare")
        cable = build_cable_with_terminations(label="CE-cable-bare", site=site)
        assert _filter({"connected_to_cable_end": [f"{cable.pk}:A"]}).qs.count() == 0

    def test_an_unknown_cable_matches_nothing(self, topology):
        assert _filter({"connected_to_cable_end": ["99999999:A"]}).qs.count() == 0

    def test_malformed_value_is_a_validation_error(self, topology):
        result = _filter({"connected_to_cable_end": ["12"]})
        assert result.is_valid() is False
        assert "connected_to_cable_end" in result.errors

    def test_an_unknown_cable_end_is_a_validation_error(self, topology):
        assert _filter({"connected_to_cable_end": ["12:C"]}).is_valid() is False

    def test_null_is_a_no_op(self, topology):
        assert _filter({"connected_to_cable_end": ["null"]}).qs.count() == 2
