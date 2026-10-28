"""GraphQL object types for netbox_pathways models."""

from typing import Annotated

import strawberry
import strawberry_django
from netbox.graphql.types import NetBoxObjectType

from ..models import (
    CableSegment,
    CircuitGeometry,
    ConduitJunction,
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
    "PathwayType",
    "ConduitJunctionType",
    "PathwayLocationType",
    "CableSegmentType",
    "PlannedRouteType",
)


@strawberry_django.type(Structure, exclude=["geometry"])
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


@strawberry_django.type(Pathway, exclude=["geometry", "path"])
class PathwayType(NetBoxObjectType):
    """GraphQL type for Pathway (geometry omitted, use the GeoJSON API)."""

    # ColorField has no strawberry mapping; core declares it the same way.
    color: str
    children: list[Annotated["PathwayType", strawberry.lazy(".types")]]
    junctions_on_trunk: list[Annotated["ConduitJunctionType", strawberry.lazy(".types")]]
    junction_as_branch: list[Annotated["ConduitJunctionType", strawberry.lazy(".types")]]
    waypoints: list[Annotated["PathwayLocationType", strawberry.lazy(".types")]]
    cable_segments: list[Annotated["CableSegmentType", strawberry.lazy(".types")]]


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
