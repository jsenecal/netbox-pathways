"""GraphQL object types for netbox_pathways models."""

from typing import Annotated

import strawberry
import strawberry_django
from netbox.graphql.types import NetBoxObjectType

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
)


@strawberry_django.type(Structure, exclude=["location"])
class StructureType(NetBoxObjectType):
    """GraphQL type for Structure (geometry omitted; use the GeoJSON API)."""

    pathways_out: list[Annotated["PathwayType", strawberry.lazy(".types")]]
    pathways_in: list[Annotated["PathwayType", strawberry.lazy(".types")]]


@strawberry_django.type(SiteGeometry, exclude=["geometry"])
class SiteGeometryType(NetBoxObjectType):
    """GraphQL type for SiteGeometry (geometry omitted; use the GeoJSON API)."""


@strawberry_django.type(CircuitGeometry, exclude=["path"])
class CircuitGeometryType(NetBoxObjectType):
    """GraphQL type for CircuitGeometry (geometry omitted; use the GeoJSON API)."""


@strawberry_django.type(Pathway, exclude=["path"])
class PathwayType(NetBoxObjectType):
    """GraphQL type for Pathway (base; geometry omitted, use the GeoJSON API)."""

    waypoints: list[Annotated["PathwayLocationType", strawberry.lazy(".types")]]
    cable_segments: list[Annotated["CableSegmentType", strawberry.lazy(".types")]]


@strawberry_django.type(ConduitBank, exclude=["path"])
class ConduitBankType(NetBoxObjectType):
    """GraphQL type for ConduitBank."""

    conduits: list[Annotated["ConduitType", strawberry.lazy(".types")]]


@strawberry_django.type(Conduit, exclude=["path"])
class ConduitType(NetBoxObjectType):
    """GraphQL type for Conduit."""

    innerducts: list[Annotated["InnerductType", strawberry.lazy(".types")]]
    junctions_on_trunk: list[Annotated["ConduitJunctionType", strawberry.lazy(".types")]]
    junction_as_branch: list[Annotated["ConduitJunctionType", strawberry.lazy(".types")]]


@strawberry_django.type(AerialSpan, exclude=["path"])
class AerialSpanType(NetBoxObjectType):
    """GraphQL type for AerialSpan."""


@strawberry_django.type(DirectBuried, exclude=["path"])
class DirectBuriedType(NetBoxObjectType):
    """GraphQL type for DirectBuried."""


@strawberry_django.type(Innerduct, exclude=["path"])
class InnerductType(NetBoxObjectType):
    """GraphQL type for Innerduct."""


@strawberry_django.type(ConduitJunction, fields="__all__")
class ConduitJunctionType(NetBoxObjectType):
    """GraphQL type for ConduitJunction."""


@strawberry_django.type(PathwayLocation, fields="__all__")
class PathwayLocationType(NetBoxObjectType):
    """GraphQL type for PathwayLocation."""


@strawberry_django.type(CableSegment, fields="__all__")
class CableSegmentType(NetBoxObjectType):
    """GraphQL type for CableSegment."""


@strawberry_django.type(PlannedRoute, fields="__all__")
class PlannedRouteType(NetBoxObjectType):
    """GraphQL type for PlannedRoute."""
