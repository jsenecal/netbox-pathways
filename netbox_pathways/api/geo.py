"""
GeoJSON API endpoints for QGIS and other GIS client consumption.

Uses djangorestframework-gis GeoFeatureModelSerializer to produce
standard GeoJSON FeatureCollections from the existing models.
"""

from django.db.models import Count
from rest_framework import serializers as drf_serializers
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filters, models

# --- GeoJSON Serializers ---

class StructureGeoSerializer(GeoFeatureModelSerializer):
    site_name = drf_serializers.CharField(source='site.name', read_only=True)
    structure_type_display = drf_serializers.CharField(
        source='get_structure_type_display', read_only=True,
    )

    class Meta:
        model = models.Structure
        geo_field = 'location'
        fields = [
            'id', 'name', 'structure_type', 'structure_type_display',
            'site', 'site_name', 'elevation', 'owner',
            'installation_date',
        ]


class PathwayGeoSerializer(GeoFeatureModelSerializer):
    pathway_type_display = drf_serializers.CharField(
        source='get_pathway_type_display', read_only=True,
    )
    start_name = drf_serializers.SerializerMethodField()
    end_name = drf_serializers.SerializerMethodField()
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Pathway
        geo_field = 'path'
        fields = [
            'id', 'name', 'pathway_type', 'pathway_type_display',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'start_name', 'end_name',
            'length', 'cables_routed', 'installation_date',
        ]

    def get_start_name(self, obj):
        ep = obj.start_endpoint
        return str(ep) if ep else None

    def get_end_name(self, obj):
        ep = obj.end_endpoint
        return str(ep) if ep else None


class ConduitGeoSerializer(GeoFeatureModelSerializer):
    material_display = drf_serializers.CharField(
        source='get_material_display', read_only=True,
    )
    start_name = drf_serializers.SerializerMethodField()
    end_name = drf_serializers.SerializerMethodField()
    conduit_bank_name = drf_serializers.CharField(
        source='conduit_bank.name', read_only=True, default=None,
    )
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Conduit
        geo_field = 'path'
        fields = [
            'id', 'name', 'material', 'material_display',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'start_name', 'end_name',
            'inner_diameter', 'outer_diameter', 'depth',
            'conduit_bank', 'conduit_bank_name', 'bank_position',
            'length', 'cables_routed', 'installation_date',
        ]

    def get_start_name(self, obj):
        ep = obj.start_endpoint
        return str(ep) if ep else None

    def get_end_name(self, obj):
        ep = obj.end_endpoint
        return str(ep) if ep else None


class AerialSpanGeoSerializer(GeoFeatureModelSerializer):
    aerial_type_display = drf_serializers.CharField(
        source='get_aerial_type_display', read_only=True,
    )
    start_name = drf_serializers.SerializerMethodField()
    end_name = drf_serializers.SerializerMethodField()
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = models.AerialSpan
        geo_field = 'path'
        fields = [
            'id', 'name', 'aerial_type', 'aerial_type_display',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'start_name', 'end_name',
            'attachment_height', 'sag', 'messenger_size',
            'length', 'cables_routed', 'installation_date',
        ]

    def get_start_name(self, obj):
        ep = obj.start_endpoint
        return str(ep) if ep else None

    def get_end_name(self, obj):
        ep = obj.end_endpoint
        return str(ep) if ep else None


class DirectBuriedGeoSerializer(GeoFeatureModelSerializer):
    start_name = drf_serializers.SerializerMethodField()
    end_name = drf_serializers.SerializerMethodField()
    cables_routed = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = models.DirectBuried
        geo_field = 'path'
        fields = [
            'id', 'name',
            'start_structure', 'end_structure',
            'start_location', 'end_location',
            'start_name', 'end_name',
            'burial_depth', 'warning_tape', 'tracer_wire',
            'length', 'cables_routed', 'installation_date',
        ]

    def get_start_name(self, obj):
        ep = obj.start_endpoint
        return str(ep) if ep else None

    def get_end_name(self, obj):
        ep = obj.end_endpoint
        return str(ep) if ep else None


# --- GeoJSON ViewSets (read-only) ---

class StructureGeoViewSet(ReadOnlyModelViewSet):
    queryset = models.Structure.objects.select_related('site').all()
    serializer_class = StructureGeoSerializer
    filterset_class = filters.StructureFilterSet


class PathwayGeoViewSet(ReadOnlyModelViewSet):
    queryset = models.Pathway.objects.select_related(
        'start_structure', 'end_structure',
        'start_location', 'end_location',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = PathwayGeoSerializer
    filterset_class = filters.PathwayFilterSet


class ConduitGeoViewSet(ReadOnlyModelViewSet):
    queryset = models.Conduit.objects.select_related(
        'start_structure', 'end_structure',
        'start_location', 'end_location',
        'conduit_bank',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = ConduitGeoSerializer
    filterset_class = filters.ConduitFilterSet


class AerialSpanGeoViewSet(ReadOnlyModelViewSet):
    queryset = models.AerialSpan.objects.select_related(
        'start_structure', 'end_structure',
        'start_location', 'end_location',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = AerialSpanGeoSerializer
    filterset_class = filters.AerialSpanFilterSet


class DirectBuriedGeoViewSet(ReadOnlyModelViewSet):
    queryset = models.DirectBuried.objects.select_related(
        'start_structure', 'end_structure',
        'start_location', 'end_location',
    ).annotate(cables_routed=Count('cable_segments'))
    serializer_class = DirectBuriedGeoSerializer
    filterset_class = filters.DirectBuriedFilterSet
