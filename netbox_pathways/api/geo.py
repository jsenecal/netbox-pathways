"""
GeoJSON API endpoints for map and GIS client consumption.

Geometries are transformed to WGS84 (EPSG:4326) in the database query
via ST_Transform, avoiding per-row Python transforms.
"""

from django.contrib.gis.db.models.functions import Transform
from django.contrib.gis.geos import Polygon
from rest_framework import serializers as drf_serializers
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filters, models
from ..geo import LEAFLET_SRID, get_srid

MAX_GEO_RESULTS = 2000


# --- GeoJSON Serializers ---
# geo_field points to an annotated field (already WGS84), declared explicitly
# so DRF doesn't try to introspect the model for it.


class StructureGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    site_name = drf_serializers.CharField(source='site.name', read_only=True)

    class Meta:
        model = models.Structure
        geo_field = 'geo_4326'
        fields = ['id', 'name', 'structure_type', 'site_name']


class PathwayGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.Pathway
        geo_field = 'geo_4326'
        fields = ['id', 'name', 'pathway_type']


class ConduitGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.Conduit
        geo_field = 'geo_4326'
        fields = ['id', 'name']


class AerialSpanGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.AerialSpan
        geo_field = 'geo_4326'
        fields = ['id', 'name']


class DirectBuriedGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.DirectBuried
        geo_field = 'geo_4326'
        fields = ['id', 'name']


# --- Bbox filtering mixin ---

class BboxFilterMixin:
    """
    Filter queryset by bounding box via ``?bbox=west,south,east,north`` (WGS84).
    Annotates a ``geo_4326`` field with the geometry transformed to WGS84.
    Caps results at MAX_GEO_RESULTS.
    """
    bbox_geo_field = 'location'  # native geometry column name

    def get_queryset(self):
        qs = super().get_queryset()

        # DB-level SRID transform — avoids per-row Python transform
        qs = qs.annotate(geo_4326=Transform(self.bbox_geo_field, LEAFLET_SRID))

        bbox = self.request.query_params.get('bbox')
        if bbox:
            try:
                west, south, east, north = (float(v) for v in bbox.split(','))
                bbox_poly = Polygon.from_bbox((west, south, east, north))
                bbox_poly.srid = LEAFLET_SRID
                if get_srid() != LEAFLET_SRID:
                    bbox_poly.transform(get_srid())
                qs = qs.filter(**{f'{self.bbox_geo_field}__intersects': bbox_poly})
            except (ValueError, TypeError):
                pass

        return qs[:MAX_GEO_RESULTS]


# --- GeoJSON ViewSets (read-only, unpaginated) ---


class StructureGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.Structure.objects.select_related('site').only(
        'id', 'name', 'structure_type', 'location', 'site__name',
    ).order_by('pk')
    serializer_class = StructureGeoSerializer
    filterset_class = filters.StructureFilterSet
    bbox_geo_field = 'location'
    pagination_class = None


class PathwayGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.Pathway.objects.only(
        'id', 'name', 'pathway_type', 'path',
    ).order_by('pk')
    serializer_class = PathwayGeoSerializer
    filterset_class = filters.PathwayFilterSet
    bbox_geo_field = 'path'
    pagination_class = None


class ConduitGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.Conduit.objects.only(
        'id', 'name', 'path',
    ).order_by('pk')
    serializer_class = ConduitGeoSerializer
    filterset_class = filters.ConduitFilterSet
    bbox_geo_field = 'path'
    pagination_class = None


class AerialSpanGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.AerialSpan.objects.only(
        'id', 'name', 'path',
    ).order_by('pk')
    serializer_class = AerialSpanGeoSerializer
    filterset_class = filters.AerialSpanFilterSet
    bbox_geo_field = 'path'
    pagination_class = None


class DirectBuriedGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.DirectBuried.objects.only(
        'id', 'name', 'path',
    ).order_by('pk')
    serializer_class = DirectBuriedGeoSerializer
    filterset_class = filters.DirectBuriedFilterSet
    bbox_geo_field = 'path'
    pagination_class = None
