"""
GeoJSON API endpoints for QGIS and other GIS client consumption.

Uses djangorestframework-gis GeoFeatureModelSerializer to produce
standard GeoJSON FeatureCollections from the existing models.

Geometries are stored in the plugin's configured SRID and transformed
to WGS84 (EPSG:4326) on output per GeoJSON RFC 7946.
"""

from django.db.models import Count
from rest_framework import serializers as drf_serializers
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filters, models
from ..geo import LEAFLET_SRID, get_srid


class Wgs84GeoFeatureModelSerializer(GeoFeatureModelSerializer):
    """GeoFeatureModelSerializer that transforms geometry to WGS84 on output."""

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        if get_srid() != LEAFLET_SRID and rep.get('geometry'):
            geo_field = self.Meta.geo_field
            geom = getattr(instance, geo_field, None)
            if geom is not None:
                clone = geom.clone()
                clone.transform(LEAFLET_SRID)
                from rest_framework_gis.fields import GeometryField as GeoField
                rep['geometry'] = GeoField().to_representation(clone)
        return rep

# --- GeoJSON Serializers ---

class StructureGeoSerializer(Wgs84GeoFeatureModelSerializer):
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


class PathwayGeoSerializer(Wgs84GeoFeatureModelSerializer):
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


class ConduitGeoSerializer(Wgs84GeoFeatureModelSerializer):
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


class AerialSpanGeoSerializer(Wgs84GeoFeatureModelSerializer):
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


class DirectBuriedGeoSerializer(Wgs84GeoFeatureModelSerializer):
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
