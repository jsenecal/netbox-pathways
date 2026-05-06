"""Smoke tests for the netbox_pathways GraphQL layer (types, filters, schema)."""

import pytest


class TestGraphQLTypeImports:
    """Verify all GraphQL type classes import cleanly."""

    def test_import_structure_type(self):
        from netbox_pathways.graphql.types import StructureType

        assert StructureType is not None

    def test_import_site_geometry_type(self):
        from netbox_pathways.graphql.types import SiteGeometryType

        assert SiteGeometryType is not None

    def test_import_circuit_geometry_type(self):
        from netbox_pathways.graphql.types import CircuitGeometryType

        assert CircuitGeometryType is not None

    def test_import_conduit_bank_type(self):
        from netbox_pathways.graphql.types import ConduitBankType

        assert ConduitBankType is not None

    def test_import_pathway_type(self):
        from netbox_pathways.graphql.types import PathwayType

        assert PathwayType is not None

    def test_import_conduit_type(self):
        from netbox_pathways.graphql.types import ConduitType

        assert ConduitType is not None

    def test_import_aerial_span_type(self):
        from netbox_pathways.graphql.types import AerialSpanType

        assert AerialSpanType is not None

    def test_import_direct_buried_type(self):
        from netbox_pathways.graphql.types import DirectBuriedType

        assert DirectBuriedType is not None

    def test_import_innerduct_type(self):
        from netbox_pathways.graphql.types import InnerductType

        assert InnerductType is not None

    def test_import_conduit_junction_type(self):
        from netbox_pathways.graphql.types import ConduitJunctionType

        assert ConduitJunctionType is not None

    def test_import_pathway_location_type(self):
        from netbox_pathways.graphql.types import PathwayLocationType

        assert PathwayLocationType is not None

    def test_import_cable_segment_type(self):
        from netbox_pathways.graphql.types import CableSegmentType

        assert CableSegmentType is not None

    def test_import_planned_route_type(self):
        from netbox_pathways.graphql.types import PlannedRouteType

        assert PlannedRouteType is not None

    def test_types_all_exports(self):
        """Verify __all__ contains exactly the expected types."""
        from netbox_pathways.graphql import types

        expected = {
            "StructureType",
            "SiteGeometryType",
            "CircuitGeometryType",
            "ConduitBankType",
            "PathwayType",
            "ConduitType",
            "AerialSpanType",
            "DirectBuriedType",
            "InnerductType",
            "ConduitJunctionType",
            "PathwayLocationType",
            "CableSegmentType",
            "PlannedRouteType",
        }
        assert set(types.__all__) == expected


class TestGraphQLFilterImports:
    """Verify all GraphQL filter classes import cleanly."""

    def test_import_structure_filter(self):
        from netbox_pathways.graphql.filters import StructureFilter

        assert StructureFilter is not None

    def test_import_site_geometry_filter(self):
        from netbox_pathways.graphql.filters import SiteGeometryFilter

        assert SiteGeometryFilter is not None

    def test_import_circuit_geometry_filter(self):
        from netbox_pathways.graphql.filters import CircuitGeometryFilter

        assert CircuitGeometryFilter is not None

    def test_import_conduit_bank_filter(self):
        from netbox_pathways.graphql.filters import ConduitBankFilter

        assert ConduitBankFilter is not None

    def test_import_pathway_filter(self):
        from netbox_pathways.graphql.filters import PathwayFilter

        assert PathwayFilter is not None

    def test_import_conduit_filter(self):
        from netbox_pathways.graphql.filters import ConduitFilter

        assert ConduitFilter is not None

    def test_import_aerial_span_filter(self):
        from netbox_pathways.graphql.filters import AerialSpanFilter

        assert AerialSpanFilter is not None

    def test_import_direct_buried_filter(self):
        from netbox_pathways.graphql.filters import DirectBuriedFilter

        assert DirectBuriedFilter is not None

    def test_import_innerduct_filter(self):
        from netbox_pathways.graphql.filters import InnerductFilter

        assert InnerductFilter is not None

    def test_import_conduit_junction_filter(self):
        from netbox_pathways.graphql.filters import ConduitJunctionFilter

        assert ConduitJunctionFilter is not None

    def test_import_pathway_location_filter(self):
        from netbox_pathways.graphql.filters import PathwayLocationFilter

        assert PathwayLocationFilter is not None

    def test_import_cable_segment_filter(self):
        from netbox_pathways.graphql.filters import CableSegmentFilter

        assert CableSegmentFilter is not None

    def test_import_planned_route_filter(self):
        from netbox_pathways.graphql.filters import PlannedRouteFilter

        assert PlannedRouteFilter is not None

    def test_filters_all_exports(self):
        """Verify __all__ contains exactly the expected filters."""
        from netbox_pathways.graphql import filters

        expected = {
            "StructureFilter",
            "SiteGeometryFilter",
            "CircuitGeometryFilter",
            "ConduitBankFilter",
            "PathwayFilter",
            "ConduitFilter",
            "AerialSpanFilter",
            "DirectBuriedFilter",
            "InnerductFilter",
            "ConduitJunctionFilter",
            "PathwayLocationFilter",
            "CableSegmentFilter",
            "PlannedRouteFilter",
        }
        assert set(filters.__all__) == expected


class TestGraphQLSchema:
    """Verify the schema query class and its fields."""

    def test_import_schema(self):
        from netbox_pathways.graphql.schema import NetBoxPathwaysQuery

        assert NetBoxPathwaysQuery is not None

    def test_schema_list(self):
        from netbox_pathways.graphql.schema import schema

        assert isinstance(schema, list)
        assert len(schema) == 1

    def _get_strawberry_field_names(self):
        from netbox_pathways.graphql.schema import NetBoxPathwaysQuery

        defn = NetBoxPathwaysQuery.__strawberry_definition__
        return {f.name for f in defn.fields}

    def test_query_has_structure_fields(self):
        fields = self._get_strawberry_field_names()
        assert "structure" in fields
        assert "structure_list" in fields

    def test_query_has_site_geometry_fields(self):
        fields = self._get_strawberry_field_names()
        assert "site_geometry" in fields
        assert "site_geometry_list" in fields

    def test_query_has_circuit_geometry_fields(self):
        fields = self._get_strawberry_field_names()
        assert "circuit_geometry" in fields
        assert "circuit_geometry_list" in fields

    def test_query_has_conduit_bank_fields(self):
        fields = self._get_strawberry_field_names()
        assert "conduit_bank" in fields
        assert "conduit_bank_list" in fields

    def test_query_has_pathway_fields(self):
        fields = self._get_strawberry_field_names()
        assert "pathway" in fields
        assert "pathway_list" in fields

    def test_query_has_conduit_fields(self):
        fields = self._get_strawberry_field_names()
        assert "conduit" in fields
        assert "conduit_list" in fields

    def test_query_has_aerial_span_fields(self):
        fields = self._get_strawberry_field_names()
        assert "aerial_span" in fields
        assert "aerial_span_list" in fields

    def test_query_has_direct_buried_fields(self):
        fields = self._get_strawberry_field_names()
        assert "direct_buried" in fields
        assert "direct_buried_list" in fields

    def test_query_has_innerduct_fields(self):
        fields = self._get_strawberry_field_names()
        assert "innerduct" in fields
        assert "innerduct_list" in fields

    def test_query_has_conduit_junction_fields(self):
        fields = self._get_strawberry_field_names()
        assert "conduit_junction" in fields
        assert "conduit_junction_list" in fields

    def test_query_has_pathway_location_fields(self):
        fields = self._get_strawberry_field_names()
        assert "pathway_location" in fields
        assert "pathway_location_list" in fields

    def test_query_has_cable_segment_fields(self):
        fields = self._get_strawberry_field_names()
        assert "cable_segment" in fields
        assert "cable_segment_list" in fields

    def test_query_has_planned_route_fields(self):
        fields = self._get_strawberry_field_names()
        assert "planned_route" in fields
        assert "planned_route_list" in fields

    def test_query_field_count(self):
        """Verify the query class has the expected number of field pairs (13 models x 2)."""
        fields = self._get_strawberry_field_names()
        assert len(fields) == 26


class TestPluginConfigGraphQLWiring:
    """Verify the plugin config exposes the GraphQL schema."""

    def test_plugin_config_resolves_graphql_schema(self):
        from netbox_pathways import NetBoxPathwaysConfig

        cfg = NetBoxPathwaysConfig.create("netbox_pathways")
        loaded = cfg._load_resource("graphql_schema")
        assert loaded is not None
        assert isinstance(loaded, list)
        assert len(loaded) == 1


@pytest.mark.django_db
class TestGraphQLFilterInstantiation:
    """Verify filter classes can be instantiated with default None values."""

    def test_structure_filter_instantiation(self):
        from netbox_pathways.graphql.filters import StructureFilter

        f = StructureFilter(id=None, name=None, status=None, structure_type=None, site_id=None, tenant_id=None)
        assert f.name is None

    def test_pathway_filter_instantiation(self):
        from netbox_pathways.graphql.filters import PathwayFilter

        f = PathwayFilter(
            id=None,
            label=None,
            pathway_type=None,
            start_structure_id=None,
            end_structure_id=None,
            start_location_id=None,
            end_location_id=None,
            tenant_id=None,
        )
        assert f.label is None

    def test_conduit_filter_instantiation(self):
        from netbox_pathways.graphql.filters import ConduitFilter

        f = ConduitFilter(id=None, material=None, conduit_bank_id=None)
        assert f.material is None

    def test_planned_route_filter_instantiation(self):
        from netbox_pathways.graphql.filters import PlannedRouteFilter

        f = PlannedRouteFilter(id=None, name=None, status=None, cable_id=None, tenant_id=None)
        assert f.status is None
