"""GraphQL schema definition for netbox_pathways plugin."""

import strawberry
import strawberry_django

from .types import (
    AerialSpanType,
    CableSegmentType,
    CircuitGeometryType,
    ConduitBankType,
    ConduitJunctionType,
    ConduitType,
    DirectBuriedType,
    InnerductType,
    PathwayLocationType,
    PathwayType,
    PlannedRouteType,
    SiteGeometryType,
    StructureType,
)


@strawberry.type(name="Query")
class NetBoxPathwaysQuery:
    """Root GraphQL query type exposing all netbox_pathways models."""

    structure: StructureType = strawberry_django.field()
    structure_list: list[StructureType] = strawberry_django.field()

    site_geometry: SiteGeometryType = strawberry_django.field()
    site_geometry_list: list[SiteGeometryType] = strawberry_django.field()

    circuit_geometry: CircuitGeometryType = strawberry_django.field()
    circuit_geometry_list: list[CircuitGeometryType] = strawberry_django.field()

    conduit_bank: ConduitBankType = strawberry_django.field()
    conduit_bank_list: list[ConduitBankType] = strawberry_django.field()

    pathway: PathwayType = strawberry_django.field()
    pathway_list: list[PathwayType] = strawberry_django.field()

    conduit: ConduitType = strawberry_django.field()
    conduit_list: list[ConduitType] = strawberry_django.field()

    aerial_span: AerialSpanType = strawberry_django.field()
    aerial_span_list: list[AerialSpanType] = strawberry_django.field()

    direct_buried: DirectBuriedType = strawberry_django.field()
    direct_buried_list: list[DirectBuriedType] = strawberry_django.field()

    innerduct: InnerductType = strawberry_django.field()
    innerduct_list: list[InnerductType] = strawberry_django.field()

    conduit_junction: ConduitJunctionType = strawberry_django.field()
    conduit_junction_list: list[ConduitJunctionType] = strawberry_django.field()

    pathway_location: PathwayLocationType = strawberry_django.field()
    pathway_location_list: list[PathwayLocationType] = strawberry_django.field()

    cable_segment: CableSegmentType = strawberry_django.field()
    cable_segment_list: list[CableSegmentType] = strawberry_django.field()

    planned_route: PlannedRouteType = strawberry_django.field()
    planned_route_list: list[PlannedRouteType] = strawberry_django.field()


schema = [NetBoxPathwaysQuery]
