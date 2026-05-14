"""Tests for plugin-owned filterset custom methods.

Covers the custom `filter_*` callbacks and the per-class `search()` overrides
in `netbox_pathways.filters`. Framework filter behaviour (django-filter,
ModelMultipleChoiceFilter, etc.) is intentionally not exercised here.
"""

import pytest
from django.contrib.gis.geos import LineString, Point
from django.db.models.signals import pre_save

from netbox_pathways.filters import (
    AerialSpanFilterSet,
    CableSegmentFilterSet,
    CircuitGeometryFilterSet,
    ConduitBankFilterSet,
    ConduitFilterSet,
    ConduitJunctionFilterSet,
    DirectBuriedFilterSet,
    InnerductFilterSet,
    PathwayFilterSet,
    PathwayLocationFilterSet,
    PlannedRouteFilterSet,
    SiteGeometryFilterSet,
    StructureFilterSet,
)
from netbox_pathways.geo import get_srid
from netbox_pathways.models import (
    AerialSpan,
    CableSegment,
    CircuitGeometry,
    Conduit,
    ConduitBank,
    ConduitJunction,
    DirectBuried,
    Innerduct,
    Pathway,
    PathwayLocation,
    PlannedRoute,
    SiteGeometry,
    Structure,
)

SRID = get_srid()


@pytest.fixture
def _disable_routability_signal():
    """Disconnect the pre_save routability check so we can build orphan segments."""
    from netbox_pathways.signals import enforce_cable_routability

    pre_save.disconnect(enforce_cable_routability, sender=CableSegment)
    yield
    pre_save.connect(enforce_cable_routability, sender=CableSegment)


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
        location=Point(0, 0, srid=SRID),
        tenant=tenant,
        access_notes="access via gate B",
    )
    s_end = Structure.objects.create(
        name="connected-end",
        location=Point(100, 0, srid=SRID),
    )
    s_isolated = Structure.objects.create(
        name="alone",
        location=Point(500, 500, srid=SRID),
    )

    # Generic Pathway (no subclass) - used for searchable label tests.
    pw = Pathway.objects.create(
        label="searchable-pathway",
        pathway_type="conduit",
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="pw-only-comment-text",
    )

    conduit = Conduit.objects.create(
        label="searchable-conduit",
        path=LineString((0, 10), (100, 10), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="conduit-only-comment-text",
    )

    aerial = AerialSpan.objects.create(
        label="searchable-aerial",
        path=LineString((0, 20), (100, 20), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="aerial-only-comment-text",
    )

    direct = DirectBuried.objects.create(
        label="searchable-direct",
        path=LineString((0, 30), (100, 30), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="direct-only-comment-text",
    )

    bank = ConduitBank.objects.create(
        label="searchable-bank",
        path=LineString((0, 40), (100, 40), srid=SRID),
        start_structure=s_start,
        end_structure=s_end,
        comments="bank-only-comment-text",
    )

    # Innerduct lives inside a parent Conduit.
    innerduct = Innerduct.objects.create(
        label="searchable-innerduct",
        path=LineString((0, 10), (100, 10), srid=SRID),
        parent_conduit=conduit,
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
        "direct": direct,
        "bank": bank,
        "innerduct": innerduct,
        "junction": junction,
        "cable": cable,
        "segment": segment,
        "waypoint": waypoint,
        "site_geom": site_geom,
        "circuit_geom": circuit_geom,
        "planned": planned,
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


@pytest.mark.django_db
class TestPathwayFilterOccupied:
    def test_true_returns_only_pathways_with_cable_segments(self, topology):
        fs = PathwayFilterSet({"occupied": True}, queryset=Pathway.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert topology["pw"].pk in pks
        # Other pathways have no CableSegment rows.
        assert topology["conduit"].pk not in pks
        assert topology["aerial"].pk not in pks

    def test_false_excludes_pathways_with_cable_segments(self, topology):
        fs = PathwayFilterSet({"occupied": False}, queryset=Pathway.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert topology["pw"].pk not in pks
        assert topology["conduit"].pk in pks


@pytest.mark.django_db
class TestPathwayFilterStructure:
    def test_returns_pathways_with_structure_at_either_end(self, topology):
        # Map queryset excludes innerducts; we expect the regular pathways but
        # not the innerduct (and not bank-member conduits, but none exist here).
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
# ConduitFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConduitSearch:
    def test_search_by_label_substring(self, topology):
        fs = ConduitFilterSet({"q": "searchable-conduit"}, queryset=Conduit.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["conduit"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = ConduitFilterSet({"q": "conduit-only-comment-text"}, queryset=Conduit.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["conduit"].pk}

    def test_search_whitespace_only_returns_full_queryset(self, topology):
        fs = ConduitFilterSet({"q": "   "}, queryset=Conduit.objects.all())
        assert fs.qs.count() == Conduit.objects.count()


# ---------------------------------------------------------------------------
# AerialSpanFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAerialSpanSearch:
    def test_search_by_label_substring(self, topology):
        fs = AerialSpanFilterSet({"q": "searchable-aerial"}, queryset=AerialSpan.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["aerial"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = AerialSpanFilterSet({"q": "aerial-only-comment-text"}, queryset=AerialSpan.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["aerial"].pk}


# ---------------------------------------------------------------------------
# DirectBuriedFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDirectBuriedSearch:
    def test_search_by_label_substring(self, topology):
        fs = DirectBuriedFilterSet({"q": "searchable-direct"}, queryset=DirectBuried.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["direct"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = DirectBuriedFilterSet({"q": "direct-only-comment-text"}, queryset=DirectBuried.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["direct"].pk}


# ---------------------------------------------------------------------------
# InnerductFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInnerductSearch:
    def test_search_by_label_substring(self, topology):
        fs = InnerductFilterSet({"q": "searchable-innerduct"}, queryset=Innerduct.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["innerduct"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = InnerductFilterSet(
            {"q": "innerduct-only-comment-text"},
            queryset=Innerduct.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["innerduct"].pk}


# ---------------------------------------------------------------------------
# ConduitBankFilterSet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestConduitBankSearch:
    def test_search_by_label_substring(self, topology):
        fs = ConduitBankFilterSet({"q": "searchable-bank"}, queryset=ConduitBank.objects.all())
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["bank"].pk}

    def test_search_by_comments_substring(self, topology):
        fs = ConduitBankFilterSet(
            {"q": "bank-only-comment-text"},
            queryset=ConduitBank.objects.all(),
        )
        pks = set(fs.qs.values_list("pk", flat=True))
        assert pks == {topology["bank"].pk}


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
