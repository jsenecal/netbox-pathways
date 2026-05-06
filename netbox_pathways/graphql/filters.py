"""GraphQL filter types for netbox_pathways models."""

import strawberry_django

from ..models import (
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

__all__ = (
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
)


@strawberry_django.filter_type(Structure)
class StructureFilter:
    """GraphQL filter for Structure."""

    id: int | None
    name: str | None
    status: str | None
    structure_type: str | None
    site_id: int | None
    tenant_id: int | None


@strawberry_django.filter_type(SiteGeometry)
class SiteGeometryFilter:
    """GraphQL filter for SiteGeometry."""

    id: int | None
    site_id: int | None
    structure_id: int | None


@strawberry_django.filter_type(CircuitGeometry)
class CircuitGeometryFilter:
    """GraphQL filter for CircuitGeometry."""

    id: int | None
    circuit_id: int | None
    provider_reference: str | None


@strawberry_django.filter_type(Pathway)
class PathwayFilter:
    """GraphQL filter for Pathway."""

    id: int | None
    label: str | None
    pathway_type: str | None
    start_structure_id: int | None
    end_structure_id: int | None
    start_location_id: int | None
    end_location_id: int | None
    tenant_id: int | None


@strawberry_django.filter_type(ConduitBank)
class ConduitBankFilter:
    """GraphQL filter for ConduitBank."""

    id: int | None
    label: str | None
    configuration: str | None
    encasement_type: str | None


@strawberry_django.filter_type(Conduit)
class ConduitFilter:
    """GraphQL filter for Conduit."""

    id: int | None
    material: str | None
    conduit_bank_id: int | None


@strawberry_django.filter_type(AerialSpan)
class AerialSpanFilter:
    """GraphQL filter for AerialSpan."""

    id: int | None
    aerial_type: str | None


@strawberry_django.filter_type(DirectBuried)
class DirectBuriedFilter:
    """GraphQL filter for DirectBuried."""

    id: int | None
    warning_tape: bool | None
    tracer_wire: bool | None


@strawberry_django.filter_type(Innerduct)
class InnerductFilter:
    """GraphQL filter for Innerduct."""

    id: int | None
    parent_conduit_id: int | None
    size: str | None
    color: str | None


@strawberry_django.filter_type(ConduitJunction)
class ConduitJunctionFilter:
    """GraphQL filter for ConduitJunction."""

    id: int | None
    label: str | None
    trunk_conduit_id: int | None
    branch_conduit_id: int | None
    towards_structure_id: int | None


@strawberry_django.filter_type(PathwayLocation)
class PathwayLocationFilter:
    """GraphQL filter for PathwayLocation."""

    id: int | None
    pathway_id: int | None
    site_id: int | None
    location_id: int | None


@strawberry_django.filter_type(CableSegment)
class CableSegmentFilter:
    """GraphQL filter for CableSegment."""

    id: int | None
    cable_id: int | None
    pathway_id: int | None
    sequence: int | None


@strawberry_django.filter_type(PlannedRoute)
class PlannedRouteFilter:
    """GraphQL filter for PlannedRoute."""

    id: int | None
    name: str | None
    status: str | None
    cable_id: int | None
    tenant_id: int | None
