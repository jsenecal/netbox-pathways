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
