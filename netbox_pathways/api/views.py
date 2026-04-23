from django.db.models import Count, Exists, OuterRef, Q
from netbox.api.viewsets import NetBoxModelViewSet

from .. import filters, models
from . import serializers


class StructureViewSet(NetBoxModelViewSet):
    queryset = models.Structure.objects.select_related('site', 'tenant').annotate(
        _has_pathways=Exists(
            models.Pathway.objects.filter(
                Q(start_structure=OuterRef('pk')) | Q(end_structure=OuterRef('pk'))
            )
        ),
    )
    serializer_class = serializers.StructureSerializer
    filterset_class = filters.StructureFilterSet


class ConduitBankViewSet(NetBoxModelViewSet):
    queryset = models.ConduitBank.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    )
    serializer_class = serializers.ConduitBankSerializer
    filterset_class = filters.ConduitBankFilterSet


class PathwayViewSet(NetBoxModelViewSet):
    queryset = models.Pathway.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = serializers.PathwaySerializer
    filterset_class = filters.PathwayFilterSet


class ConduitViewSet(NetBoxModelViewSet):
    queryset = models.Conduit.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location',
        'conduit_bank', 'start_junction', 'end_junction', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = serializers.ConduitSerializer
    filterset_class = filters.ConduitFilterSet


class AerialSpanViewSet(NetBoxModelViewSet):
    queryset = models.AerialSpan.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = serializers.AerialSpanSerializer
    filterset_class = filters.AerialSpanFilterSet


class DirectBuriedViewSet(NetBoxModelViewSet):
    queryset = models.DirectBuried.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = serializers.DirectBuriedSerializer
    filterset_class = filters.DirectBuriedFilterSet


class InnerductViewSet(NetBoxModelViewSet):
    queryset = models.Innerduct.objects.select_related(
        'parent_conduit', 'start_structure', 'end_structure',
        'start_location', 'end_location', 'tenant',
    ).annotate(
        cables_routed=Count('cable_segments'),
    )
    serializer_class = serializers.InnerductSerializer
    filterset_class = filters.InnerductFilterSet


class ConduitJunctionViewSet(NetBoxModelViewSet):
    queryset = models.ConduitJunction.objects.select_related(
        'trunk_conduit', 'branch_conduit', 'towards_structure',
    )
    serializer_class = serializers.ConduitJunctionSerializer
    filterset_class = filters.ConduitJunctionFilterSet


class PathwayLocationViewSet(NetBoxModelViewSet):
    queryset = models.PathwayLocation.objects.select_related('pathway', 'site', 'location')
    serializer_class = serializers.PathwayLocationSerializer
    filterset_class = filters.PathwayLocationFilterSet


class CableSegmentViewSet(NetBoxModelViewSet):
    queryset = models.CableSegment.objects.select_related('cable', 'pathway')
    serializer_class = serializers.CableSegmentSerializer
    filterset_class = filters.CableSegmentFilterSet


class SlackLoopViewSet(NetBoxModelViewSet):
    queryset = models.SlackLoop.objects.select_related('cable', 'structure', 'pathway')
    serializer_class = serializers.SlackLoopSerializer
    filterset_class = filters.SlackLoopFilterSet


class SiteGeometryViewSet(NetBoxModelViewSet):
    queryset = models.SiteGeometry.objects.select_related('site', 'structure')
    serializer_class = serializers.SiteGeometrySerializer
    filterset_class = filters.SiteGeometryFilterSet


class CircuitGeometryViewSet(NetBoxModelViewSet):
    queryset = models.CircuitGeometry.objects.select_related('circuit', 'circuit__provider')
    serializer_class = serializers.CircuitGeometrySerializer
    filterset_class = filters.CircuitGeometryFilterSet


class PlannedRouteViewSet(NetBoxModelViewSet):
    queryset = models.PlannedRoute.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location',
        'tenant', 'cable',
    )
    serializer_class = serializers.PlannedRouteSerializer
    filterset_class = filters.PlannedRouteFilterSet
