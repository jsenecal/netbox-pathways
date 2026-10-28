"""Tests for plugin-owned filterset custom methods.

Covers the custom `filter_*` callbacks and the per-class `search()` overrides
in `netbox_pathways.filtersets`. Framework filter behaviour (django-filter,
ModelMultipleChoiceFilter, etc.) is intentionally not exercised here.
"""

import pytest
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.filtersets import (
    CableSegmentFilterSet,
    CircuitGeometryFilterSet,
    ConduitJunctionFilterSet,
    PathwayFilterSet,
    PathwayLocationFilterSet,
    PlannedRouteFilterSet,
    SiteGeometryFilterSet,
    StructureFilterSet,
)
from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    CableSegment,
    CircuitGeometry,
    ConduitJunction,
    Pathway,
    PathwayLocation,
    PlannedRoute,
    SiteGeometry,
    Structure,
)
from netbox_pathways.pathway_types import TYPE_SPECIFIC_FIELDS

SRID = get_srid()


@pytest.fixture
def topology(db, _disable_routability_signal):
    """Distinctive-named row of each model so each `search()` test can find it."""
    from circuits.models import Circuit, CircuitType, Provider
    from dcim.models import Cable, Location, Site
    from tenancy.models import Tenant

    tenant = Tenant.objects.create(name="distinct-tenant", slug="distinct-tenant")
    site = Site.objects.create(name="distinct-site", slug="distinct-site")
    location = Location.objects.create(name="distinct-loc", slug="distinct-loc", site=site)

    s_start = Structure.objects.create(
        name="connected-start",
        geometry=Point(0, 0, srid=SRID),
        tenant=tenant,
        access_notes="access via gate B",
    )
    s_end = Structure.objects.create(
        name="connected-end",
        geometry=Point(100, 0, srid=SRID),
    )
    s_isolated = Structure.objects.create(
        name="alone",
        geometry=Point(500, 500, srid=SRID),
    )

    pw = Pathway.objects.create(
        label="searchable-pathway",
        pathway_type="conduit",
        geometry=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="pw-only-comment-text",
    )
    conduit = Pathway.objects.create(
        label="searchable-conduit",
        pathway_type="conduit",
        geometry=LineString((0, 10), (100, 10), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="conduit-only-comment-text",
    )
    aerial = Pathway.objects.create(
        label="searchable-aerial",
        pathway_type="aerial",
        geometry=LineString((0, 20), (100, 20), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="aerial-only-comment-text",
    )
    innerduct = Pathway.objects.create(
        label="searchable-innerduct",
        pathway_type="innerduct",
        parent=conduit,
        size="32mm",
        comments="innerduct-only-comment-text",
    )

    junction = ConduitJunction.objects.create(
        label="searchable-junction",
        trunk_conduit=conduit,
        branch_conduit=conduit,
        towards_structure=s_start,
        position_on_trunk=0.5,
        comments="junction-only-comment-text",
    )

    cable = Cable.objects.create(label="test-cable")
    segment = CableSegment.objects.create(
        cable=cable,
        pathway=pw,
        sequence=1,
        comments="segment-only-comment-text",
    )

    waypoint = PathwayLocation.objects.create(
        pathway=pw,
        site=site,
        location=location,
        sequence=1,
        comments="waypoint-only-comment-text",
    )

    site_geom = SiteGeometry.objects.create(site=site, structure=s_start)

    provider = Provider.objects.create(name="search-provider", slug="search-provider")
    ctype = CircuitType.objects.create(name="search-ctype", slug="search-ctype")
    circuit = Circuit.objects.create(cid="SEARCHABLE-CID", provider=provider, type=ctype)
    circuit_geom = CircuitGeometry.objects.create(
        circuit=circuit,
        path=LineString((0, 0), (1, 1), srid=SRID),
        provider_reference="REF-SEARCHABLE",
    )

    planned = PlannedRoute.objects.create(
        name="searchable-planned",
        start_structure=s_start,
        end_structure=s_end,
        pathway_ids=[pw.pk],
        comments="planned-only-comment-text",
    )

    return {
        "tenant": tenant,
        "site": site,
        "location": location,
        "s_start": s_start,
        "s_end": s_end,
        "s_isolated": s_isolated,
        "pw": pw,
        "conduit": conduit,
        "aerial": aerial,
        "innerduct": innerduct,
        "junction": junction,
        "cable": cable,
        "segment": segment,
        "waypoint": waypoint,
        "site_geom": site_geom,
        "circuit_geom": circuit_geom,
        "planned": planned,
    }


@pytest.fixture
def occupancy(db, _disable_routability_signal):
    """Containment topology for occupied-filter tests.

    One cable routed through: an aerial span (direct), an innerduct (making
    its parent conduit occupied by containment), and a bank-member conduit
    (making the bank occupied by containment). The host conduit sits inside
    a second bank to exercise the two-level innerduct -> conduit -> bank arm.
    Empty siblings of each class prove the negative side.
    """
    from dcim.models import Cable

    s_a = Structure.objects.create(name="occ-a", geometry=Point(0, 0, srid=SRID))
    s_b = Structure.objects.create(name="occ-b", geometry=Point(100, 0, srid=SRID))
    line = LineString((0, 0), (100, 0), srid=SRID)

    def make(label, pathway_type, parent=None):
        geometry = None if parent else line
        return Pathway.objects.create(
            label=label,
            pathway_type=pathway_type,
            parent=parent,
            geometry=geometry,
            start_structure=s_a,
            end_structure=s_b,
        )

    aerial = make("occ-aerial", "aerial")
    aerial_empty = make("occ-aerial-empty", "aerial")

    inner_bank = make("occ-inner-bank", "conduit_bank")
    conduit_host = make("occ-host", "conduit", parent=inner_bank)
    innerduct = make("occ-inner", "innerduct", parent=conduit_host)
    innerduct_empty = make("occ-inner-empty", "innerduct", parent=conduit_host)

    bank = make("occ-bank", "conduit_bank")
    conduit_in_bank = make("occ-banked", "conduit", parent=bank)
    conduit_empty = make("occ-empty", "conduit")
    bank_empty = make("occ-bank-empty", "conduit_bank")

    buried = make("occ-buried", "direct_buried")
    buried_duct = make("occ-buried-duct", "innerduct", parent=buried)

    cable = Cable.objects.create(label="occ-cable")
    CableSegment.objects.create(cable=cable, pathway=aerial, sequence=1)
    CableSegment.objects.create(cable=cable, pathway=innerduct, sequence=2)
    CableSegment.objects.create(cable=cable, pathway=conduit_in_bank, sequence=3)
    CableSegment.objects.create(cable=cable, pathway=buried_duct, sequence=4)

    return {
        "aerial": aerial,
        "aerial_empty": aerial_empty,
        "inner_bank": inner_bank,
        "conduit_host": conduit_host,
        "innerduct": innerduct,
        "innerduct_empty": innerduct_empty,
        "bank": bank,
        "conduit_in_bank": conduit_in_bank,
        "conduit_empty": conduit_empty,
        "bank_empty": bank_empty,
        "buried": buried,
        "buried_duct": buried_duct,
    }


# ---------------------------------------------------------------------------
# StructureFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStructureFilterOccupied:
    def test_true_returns_structures_used_as_routed_endpoints(self, topology):
        fs = StructureFilterSet({"occupied": True}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert topology["s_start"].pk in pks
        assert topology["s_end"].pk in pks
        assert topology["s_isolated"].pk not in pks

    def test_false_excludes_occupied_endpoints(self, topology):
        fs = StructureFilterSet({"occupied": False}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert topology["s_isolated"].pk in pks
        assert topology["s_start"].pk not in pks
        assert topology["s_end"].pk not in pks


@pytest.mark.django_db
class TestStructureFilterHasPathways:
    def test_true_returns_only_pathway_endpoints(self, topology):
        fs = StructureFilterSet({"has_pathways": True}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        # s_start/s_end terminate several pathways; s_isolated terminates none.
        assert topology["s_start"].pk in pks
        assert topology["s_end"].pk in pks
        assert topology["s_isolated"].pk not in pks

    def test_false_returns_only_structures_without_pathways(self, topology):
        fs = StructureFilterSet({"has_pathways": False}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["s_isolated"].pk}


@pytest.mark.django_db
class TestStructureSearch:
    def test_search_by_name_substring(self, topology):
        fs = StructureFilterSet({"q": "connected"}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["s_start"].pk, topology["s_end"].pk}

    def test_search_by_tenant_name_substring(self, topology):
        fs = StructureFilterSet({"q": "distinct-tenant"}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["s_start"].pk}

    def test_search_by_access_notes_substring(self, topology):
        fs = StructureFilterSet({"q": "gate B"}, queryset=Structure.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["s_start"].pk}

    def test_search_whitespace_only_returns_full_queryset(self, topology):
        fs = StructureFilterSet({"q": "   "}, queryset=Structure.objects.all())
        assert fs.qs.count() == Structure.objects.count()


# ---------------------------------------------------------------------------
# PathwayFilterSet
# ---------------------------------------------------------------------------


def _occupied(value):
    fs = PathwayFilterSet({"occupied": value}, queryset=Pathway.objects.all())
    return set(fs.qs.values_list("pk", flat=True))


@pytest.mark.django_db
class TestPathwayFilterOccupiedContainment:
    """A pathway is occupied when a cable runs through it or anything inside it."""

    @pytest.mark.parametrize(
        "name",
        ["aerial", "innerduct", "conduit_in_bank", "conduit_host", "bank", "inner_bank", "buried", "buried_duct"],
    )
    def test_true_includes_rows_occupied_directly_or_via_descendants(self, occupancy, name):
        assert occupancy[name].pk in _occupied(True)

    @pytest.mark.parametrize("name", ["aerial_empty", "innerduct_empty", "conduit_empty", "bank_empty"])
    def test_true_excludes_rows_with_no_cable_in_their_subtree(self, occupancy, name):
        assert occupancy[name].pk not in _occupied(True)

    def test_false_is_the_complement(self, occupancy):
        assert _occupied(False) == set(Pathway.objects.values_list("pk", flat=True)) - _occupied(True)


@pytest.fixture
def hierarchy(db):
    """Two banks; B holds conduit C, which holds innerduct I, which holds I2."""
    line = LineString((0, 0), (100, 0), srid=SRID)
    bank = Pathway.objects.create(label="h-bank", pathway_type="conduit_bank", geometry=line)
    conduit = Pathway.objects.create(label="h-conduit", pathway_type="conduit", parent=bank)
    duct = Pathway.objects.create(label="h-duct", pathway_type="innerduct", parent=conduit)
    subduct = Pathway.objects.create(label="h-subduct", pathway_type="innerduct", parent=duct)
    other_bank = Pathway.objects.create(label="h-other-bank", pathway_type="conduit_bank", geometry=line)
    other_conduit = Pathway.objects.create(label="h-other-conduit", pathway_type="conduit", parent=other_bank)
    return {
        "bank": bank,
        "conduit": conduit,
        "duct": duct,
        "subduct": subduct,
        "other_bank": other_bank,
        "other_conduit": other_conduit,
    }


def _labels(data):
    fs = PathwayFilterSet(data, queryset=Pathway.objects.all())
    assert fs.is_valid(), fs.errors
    return set(fs.qs.values_list("label", flat=True))


@pytest.mark.django_db
class TestPathwayHierarchyFilters:
    def test_ancestor_filter_returns_subtree(self, hierarchy):
        """Everything inside the bank, at any depth, but not the bank itself."""
        assert _labels({"ancestor_id": [hierarchy["bank"].pk]}) == {"h-conduit", "h-duct", "h-subduct"}

    def test_ancestor_filter_ors_several_roots(self, hierarchy):
        result = _labels({"ancestor_id": [hierarchy["duct"].pk, hierarchy["other_bank"].pk]})
        assert result == {"h-subduct", "h-other-conduit"}

    def test_descendant_filter_returns_containers(self, hierarchy):
        """Every pathway the innerduct runs inside, outermost included."""
        assert _labels({"descendant_id": [hierarchy["subduct"].pk]}) == {"h-bank", "h-conduit", "h-duct"}


@pytest.mark.django_db
def test_installed_by_filter_applies_to_every_type():
    """Regression for #175: installed_by_id was missing from the subtype filtersets."""
    from tenancy.models import Tenant

    crew = Tenant.objects.create(name="install-crew", slug="install-crew")
    line = LineString((0, 0), (100, 0), srid=SRID)
    bank = Pathway.objects.create(pathway_type="conduit_bank", geometry=line, installed_by=crew)
    conduit = Pathway.objects.create(pathway_type="conduit", parent=bank, installed_by=crew)
    raceway = Pathway.objects.create(pathway_type="raceway", installed_by=crew)
    expected = {
        bank.pk,
        conduit.pk,
        raceway.pk,
        Pathway.objects.create(pathway_type="innerduct", parent=conduit, installed_by=crew).pk,
        Pathway.objects.create(pathway_type="tray", parent=raceway, installed_by=crew).pk,
        Pathway.objects.create(pathway_type="aerial", geometry=line, installed_by=crew).pk,
        Pathway.objects.create(pathway_type="direct_buried", geometry=line, installed_by=crew).pk,
        Pathway.objects.create(pathway_type="submarine", geometry=line, installed_by=crew).pk,
    }
    Pathway.objects.create(pathway_type="submarine", geometry=line)

    fs = PathwayFilterSet({"installed_by_id": [crew.pk]}, queryset=Pathway.objects.all())
    assert set(fs.qs.values_list("pk", flat=True)) == expected


def test_every_type_specific_field_has_a_filter():
    """The filterset follows pathway_types.py: a new type field gets a filter."""
    filters = PathwayFilterSet.get_filters()
    expected = {f"{name}_id" if name.endswith("_junction") else name for name in TYPE_SPECIFIC_FIELDS}
    assert expected <= set(filters)


@pytest.mark.django_db
class TestPathwayFilterStructure:
    def test_returns_pathways_with_structure_at_either_end(self, topology):
        # Only map containers match: the innerduct inherits the conduit's
        # endpoints but is shown through the conduit, not on its own.
        fs = PathwayFilterSet(
            {"structure_id": [topology["s_start"].pk]},
            queryset=Pathway.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert topology["pw"].pk in pks
        assert topology["conduit"].pk in pks
        assert topology["innerduct"].pk not in pks

    def test_empty_value_returns_queryset_unchanged(self, topology):
        # An empty ModelMultipleChoiceFilter value short-circuits to queryset.
        all_pks = set(Pathway.objects.values_list("pk", flat=True))
        fs = PathwayFilterSet({}, queryset=Pathway.objects.all())
        assert set(fs.qs.values_list("pk", flat=True)) == all_pks


@pytest.mark.django_db
class TestPathwaySearch:
    def test_search_by_label_substring(self, topology):
        fs = PathwayFilterSet({"q": "searchable-pathway"}, queryset=Pathway.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert topology["pw"].pk in pks
        assert topology["conduit"].pk not in pks

    def test_search_by_comments_substring(self, topology):
        fs = PathwayFilterSet({"q": "pw-only-comment-text"}, queryset=Pathway.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["pw"].pk}

    def test_search_whitespace_only_returns_full_queryset(self, topology):
        fs = PathwayFilterSet({"q": "  "}, queryset=Pathway.objects.all())
        assert fs.qs.count() == Pathway.objects.count()


# ---------------------------------------------------------------------------
# ConduitJunctionFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConduitJunctionSearch:
    def test_search_by_label_substring(self, topology):
        fs = ConduitJunctionFilterSet(
            {"q": "searchable-junction"},
            queryset=ConduitJunction.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["junction"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = ConduitJunctionFilterSet(
            {"q": "junction-only-comment-text"},
            queryset=ConduitJunction.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["junction"].pk}


# ---------------------------------------------------------------------------
# CableSegmentFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCableSegmentSearch:
    def test_search_by_comments_substring(self, topology):
        fs = CableSegmentFilterSet(
            {"q": "segment-only-comment-text"},
            queryset=CableSegment.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["segment"].pk}

    def test_search_whitespace_only_returns_full_queryset(self, topology):
        fs = CableSegmentFilterSet({"q": "   "}, queryset=CableSegment.objects.all())
        assert fs.qs.count() == CableSegment.objects.count()


# ---------------------------------------------------------------------------
# PathwayLocationFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPathwayLocationSearch:
    def test_search_by_comments_substring(self, topology):
        fs = PathwayLocationFilterSet(
            {"q": "waypoint-only-comment-text"},
            queryset=PathwayLocation.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["waypoint"].pk}


# ---------------------------------------------------------------------------
# SiteGeometryFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSiteGeometrySearch:
    def test_search_by_site_name_substring(self, topology):
        fs = SiteGeometryFilterSet({"q": "distinct-site"}, queryset=SiteGeometry.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["site_geom"].pk}


# ---------------------------------------------------------------------------
# CircuitGeometryFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCircuitGeometrySearch:
    def test_search_by_circuit_cid_substring(self, topology):
        fs = CircuitGeometryFilterSet({"q": "SEARCHABLE-CID"}, queryset=CircuitGeometry.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["circuit_geom"].pk}

    def test_search_by_provider_reference_substring(self, topology):
        fs = CircuitGeometryFilterSet({"q": "REF-SEARCHABLE"}, queryset=CircuitGeometry.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["circuit_geom"].pk}


# ---------------------------------------------------------------------------
# PlannedRouteFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPlannedRouteSearch:
    def test_search_by_name_substring(self, topology):
        fs = PlannedRouteFilterSet({"q": "searchable-planned"}, queryset=PlannedRoute.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["planned"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = PlannedRouteFilterSet(
            {"q": "planned-only-comment-text"},
            queryset=PlannedRoute.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["planned"].pk}
