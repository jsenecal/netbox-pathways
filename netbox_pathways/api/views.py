from netbox.api.viewsets import NetBoxModelViewSet

from .. import filters, models
from . import serializers


class StructureViewSet(NetBoxModelViewSet):
    queryset = models.Structure.objects.all()
    serializer_class = serializers.StructureSerializer
    filterset_class = filters.StructureFilterSet


class ConduitBankViewSet(NetBoxModelViewSet):
    queryset = models.ConduitBank.objects.all()
    serializer_class = serializers.ConduitBankSerializer
    filterset_class = filters.ConduitBankFilterSet


class PathwayViewSet(NetBoxModelViewSet):
    queryset = models.Pathway.objects.all()
    serializer_class = serializers.PathwaySerializer
    filterset_class = filters.PathwayFilterSet


class ConduitViewSet(NetBoxModelViewSet):
    queryset = models.Conduit.objects.all()
    serializer_class = serializers.ConduitSerializer
    filterset_class = filters.ConduitFilterSet


class AerialSpanViewSet(NetBoxModelViewSet):
    queryset = models.AerialSpan.objects.all()
    serializer_class = serializers.AerialSpanSerializer
    filterset_class = filters.AerialSpanFilterSet


class DirectBuriedViewSet(NetBoxModelViewSet):
    queryset = models.DirectBuried.objects.all()
    serializer_class = serializers.DirectBuriedSerializer
    filterset_class = filters.DirectBuriedFilterSet


class InnerductViewSet(NetBoxModelViewSet):
    queryset = models.Innerduct.objects.all()
    serializer_class = serializers.InnerductSerializer
    filterset_class = filters.InnerductFilterSet


class ConduitJunctionViewSet(NetBoxModelViewSet):
    queryset = models.ConduitJunction.objects.all()
    serializer_class = serializers.ConduitJunctionSerializer
    filterset_class = filters.ConduitJunctionFilterSet


class PathwayLocationViewSet(NetBoxModelViewSet):
    queryset = models.PathwayLocation.objects.all()
    serializer_class = serializers.PathwayLocationSerializer
    filterset_class = filters.PathwayLocationFilterSet


class CableSegmentViewSet(NetBoxModelViewSet):
    queryset = models.CableSegment.objects.all()
    serializer_class = serializers.CableSegmentSerializer
    filterset_class = filters.CableSegmentFilterSet
