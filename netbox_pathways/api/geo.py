"""
GeoJSON API endpoints for map and GIS client consumption.

Geometries are transformed to WGS84 (EPSG:4326) in the database query
via ST_Transform, avoiding per-row Python transforms.

Structures support server-side grid clustering: when a ``zoom`` query
parameter is present and below CLUSTER_ZOOM_THRESHOLD, the API returns
cluster centroids + counts instead of individual features, dramatically
reducing payload size at low zoom levels.
"""

from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import Centroid, SnapToGrid, Transform
from django.contrib.gis.geos import Polygon
from django.db.models import Count
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filters, models
from ..geo import LEAFLET_SRID, get_srid

MAX_GEO_RESULTS = 2000
CLUSTER_ZOOM_THRESHOLD = 15  # zoom < this → server-side clustering


def _grid_size_for_zoom(zoom):
    """Grid cell size in WGS84 degrees, calibrated to ~50px cluster radius."""
    return 70.0 / (2 ** zoom)


# --- GeoJSON Serializers ---
# geo_field points to an annotated field (already WGS84), declared explicitly
# so DRF doesn't try to introspect the model for it.


class StructureGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    site_name = drf_serializers.SerializerMethodField()

    class Meta:
        model = models.Structure
        geo_field = 'geo_4326'
        fields = ['id', 'name', 'structure_type', 'site_name']

    def get_site_name(self, obj):
        return obj.site.name if obj.site_id else None


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
    """
    bbox_geo_field = 'location'  # native geometry column name

    def _apply_bbox(self, qs):
        """Annotate geo_4326 and apply bbox filter (no result cap)."""
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

        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        return self._apply_bbox(qs)[:MAX_GEO_RESULTS]


# --- GeoJSON ViewSets (read-only, unpaginated) ---


class StructureGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.Structure.objects.select_related('site').only(
        'id', 'name', 'structure_type', 'location', 'site__name',
    ).order_by('pk')
    serializer_class = StructureGeoSerializer
    filterset_class = filters.StructureFilterSet
    bbox_geo_field = 'location'
    pagination_class = None

    def list(self, request, *args, **kwargs):
        zoom = self._parse_zoom()
        if zoom is not None and zoom < CLUSTER_ZOOM_THRESHOLD:
            return self._clustered_response(zoom)
        return super().list(request, *args, **kwargs)

    def _parse_zoom(self):
        try:
            return int(self.request.query_params['zoom'])
        except (KeyError, ValueError, TypeError):
            return None

    def _clustered_response(self, zoom):
        # Get bbox-filtered queryset WITHOUT the result cap (aggregation reduces rows)
        qs = self._apply_bbox(
            models.Structure.objects.only('id', 'location').order_by()
        )

        grid_size = _grid_size_for_zoom(zoom)
        geo_expr = Transform('location', LEAFLET_SRID)
        clusters = (
            qs
            # Grid used only for grouping — the actual display point is the
            # centroid of collected geometries, giving organic placement.
            .annotate(grid_cell=SnapToGrid(geo_expr, grid_size))
            .values('grid_cell')
            .annotate(
                count=Count('id'),
                centroid=Centroid(Collect(geo_expr)),
            )
            .order_by()
        )

        features = []
        total = 0
        for c in clusters:
            pt = c['centroid']
            if pt is None:
                continue
            count = c['count']
            total += count
            features.append({
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [pt.x, pt.y],
                },
                'properties': {
                    'cluster': True,
                    'point_count': count,
                },
            })

        return Response({
            'type': 'FeatureCollection',
            'features': features,
            'total_count': total,
        })


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
