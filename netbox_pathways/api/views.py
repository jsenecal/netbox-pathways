from django.db.models import Count, Exists, OuterRef
from netbox.api.viewsets import NetBoxModelViewSet

from .. import filtersets, models
from . import serializers


class StructureViewSet(NetBoxModelViewSet):
    queryset = models.Structure.objects.select_related("site", "tenant").annotate(
        _has_pathways=Exists(models.Pathway.objects.touching(OuterRef("pk"))),
    )
    serializer_class = serializers.StructureSerializer
    filterset_class = filtersets.StructureFilterSet


class PathwayViewSet(NetBoxModelViewSet):
    queryset = models.Pathway.objects.select_related(
        "parent",
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "start_anchor",
        "end_anchor",
        "start_junction",
        "end_junction",
        "tenant",
        "installed_by",
    ).annotate(cables_routed=Count("cable_segments"))
    serializer_class = serializers.PathwaySerializer
    filterset_class = filtersets.PathwayFilterSet


class ConduitJunctionViewSet(NetBoxModelViewSet):
    queryset = models.ConduitJunction.objects.select_related(
        "trunk_conduit",
        "branch_conduit",
        "towards_structure",
    )
    serializer_class = serializers.ConduitJunctionSerializer
    filterset_class = filtersets.ConduitJunctionFilterSet


class PathwayLocationViewSet(NetBoxModelViewSet):
    queryset = models.PathwayLocation.objects.select_related("pathway", "site", "location")
    serializer_class = serializers.PathwayLocationSerializer
    filterset_class = filtersets.PathwayLocationFilterSet


class CableSegmentViewSet(NetBoxModelViewSet):
    queryset = models.CableSegment.objects.select_related("cable", "pathway")
    serializer_class = serializers.CableSegmentSerializer
    filterset_class = filtersets.CableSegmentFilterSet


class SiteGeometryViewSet(NetBoxModelViewSet):
    queryset = models.SiteGeometry.objects.select_related("site", "structure")
    serializer_class = serializers.SiteGeometrySerializer
    filterset_class = filtersets.SiteGeometryFilterSet


class CircuitGeometryViewSet(NetBoxModelViewSet):
    queryset = models.CircuitGeometry.objects.select_related("circuit", "circuit__provider")
    serializer_class = serializers.CircuitGeometrySerializer
    filterset_class = filtersets.CircuitGeometryFilterSet


class PlannedRouteViewSet(NetBoxModelViewSet):
    queryset = models.PlannedRoute.objects.select_related(
        "start_structure",
        "end_structure",
        "start_location",
        "end_location",
        "tenant",
        "cable",
    )
    serializer_class = serializers.PlannedRouteSerializer
    filterset_class = filtersets.PlannedRouteFilterSet
