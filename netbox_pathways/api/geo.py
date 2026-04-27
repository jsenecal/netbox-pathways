"""
GeoJSON API endpoints for map and GIS client consumption.

Geometries are transformed to WGS84 (EPSG:4326) in the database query
via ST_Transform, avoiding per-row Python transforms.

Structures support server-side grid clustering: when a ``zoom`` query
parameter is present and below CLUSTER_ZOOM_THRESHOLD, the API returns
cluster centroids + counts instead of individual features, dramatically
reducing payload size at low zoom levels.
"""

import hashlib

from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import Centroid, SnapToGrid, Transform
from django.contrib.gis.geos import Polygon
from django.db.models import Count, Max
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filters, models
from ..geo import LEAFLET_SRID, get_srid

MAX_GEO_RESULTS = 2000


def _grid_size_for_zoom(zoom):
    """Grid cell size in WGS84 degrees, calibrated to ~50px cluster radius."""
    return 70.0 / (2**zoom)


# --- GeoJSON Serializers ---
# geo_field points to an annotated field (already WGS84), declared explicitly
# so DRF doesn't try to introspect the model for it.
#
# NOTE: These serializers intentionally omit ``url`` (get_absolute_url).
# Calling reverse() per row is extremely expensive (~12 s / 1000 rows) due to
# lazy URL-pattern population.  The map client constructs detail URLs itself
# from featureType + id, so the field is not needed.


class StructureGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    name = drf_serializers.CharField(read_only=True)
    site_name = drf_serializers.SerializerMethodField()

    class Meta:
        model = models.Structure
        geo_field = "geo_4326"
        fields = ["id", "name", "structure_type", "site_name"]

    def get_site_name(self, obj):
        return obj.site.name if obj.site_id else None


class PathwayGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.Pathway
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type"]


class ConduitBankGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    conduit_count = drf_serializers.IntegerField(read_only=True)

    class Meta:
        model = models.ConduitBank
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type", "configuration", "conduit_count"]


class ConduitGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.Conduit
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type"]


class AerialSpanGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.AerialSpan
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type"]


class DirectBuriedGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)

    class Meta:
        model = models.DirectBuried
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type"]


class CircuitGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    cid = drf_serializers.CharField(source="circuit.cid", read_only=True)
    provider = drf_serializers.CharField(source="circuit.provider.name", read_only=True)
    circuit_type = drf_serializers.CharField(source="circuit.type.name", read_only=True)
    status = drf_serializers.CharField(source="circuit.status", read_only=True)

    class Meta:
        model = models.CircuitGeometry
        geo_field = "geo_4326"
        fields = ["id", "cid", "provider", "circuit_type", "status", "provider_reference"]


# --- Bbox filtering mixin ---


class BboxFilterMixin:
    """
    Filter queryset by bounding box via ``?bbox=west,south,east,north`` (WGS84).
    Annotates a ``geo_4326`` field with the geometry transformed to WGS84.

    The result cap (MAX_GEO_RESULTS) is applied in ``list()`` rather than
    ``get_queryset()`` so that DRF's filter backends (e.g. ``?q=``) can
    still filter the queryset before slicing.
    """

    bbox_geo_field = "location"  # native geometry column name

    def _apply_bbox(self, qs):
        """Annotate geo_4326 and apply bbox filter (no result cap)."""
        qs = qs.annotate(geo_4326=Transform(self.bbox_geo_field, LEAFLET_SRID))

        bbox = self.request.query_params.get("bbox")
        if bbox:
            try:
                west, south, east, north = (float(v) for v in bbox.split(","))
                bbox_poly = Polygon.from_bbox((west, south, east, north))
                bbox_poly.srid = LEAFLET_SRID
                if get_srid() != LEAFLET_SRID:
                    bbox_poly.transform(get_srid())
                qs = qs.filter(**{f"{self.bbox_geo_field}__intersects": bbox_poly})
            except (ValueError, TypeError):
                pass

        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        return self._apply_bbox(qs)

    def _etag_for_queryset(self, queryset):
        """Lightweight ETag from max(last_updated) + count."""
        agg = queryset.aggregate(t=Max("last_updated"), c=Count("id"))
        raw = f"{agg['t']}:{agg['c']}"
        return hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # ETag: cheap aggregate check before expensive serialization
        etag = self._etag_for_queryset(queryset)
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=304)

        # Apply the result cap after ETag check
        serializer = self.get_serializer(queryset[:MAX_GEO_RESULTS], many=True)
        response = Response(serializer.data)
        response["ETag"] = etag
        return response


# --- GeoJSON ViewSets (read-only, unpaginated) ---


class StructureGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = (
        models.Structure.objects.select_related("site")
        .only(
            "id",
            "name",
            "structure_type",
            "location",
            "site__name",
        )
        .order_by("pk")
    )
    serializer_class = StructureGeoSerializer
    filterset_class = filters.StructureFilterSet
    bbox_geo_field = "location"
    pagination_class = None

    def list(self, request, *args, **kwargs):
        zoom = self._parse_zoom()
        if zoom is not None:
            qs = self.filter_queryset(self.get_queryset())
            # ETag check before expensive count/serialize
            etag = self._etag_for_queryset(qs)
            if request.META.get("HTTP_IF_NONE_MATCH") == etag:
                return Response(status=304)
            if qs.count() > MAX_GEO_RESULTS:
                return self._clustered_response(zoom, etag)
            serializer = self.get_serializer(qs[:MAX_GEO_RESULTS], many=True)
            response = Response(serializer.data)
            response["ETag"] = etag
            return response
        return super().list(request, *args, **kwargs)

    def _parse_zoom(self):
        try:
            return int(self.request.query_params["zoom"])
        except (KeyError, ValueError, TypeError):
            return None

    def _clustered_response(self, zoom, etag=None):
        # Get bbox-filtered queryset WITHOUT the result cap (aggregation reduces rows)
        qs = self._apply_bbox(models.Structure.objects.only("id", "location").order_by())

        grid_size = _grid_size_for_zoom(zoom)
        geo_expr = Transform("location", LEAFLET_SRID)
        clusters = (
            qs
            # Grid used only for grouping — the actual display point is the
            # centroid of collected geometries, giving organic placement.
            .annotate(grid_cell=SnapToGrid(geo_expr, grid_size))
            .values("grid_cell")
            .annotate(
                count=Count("id"),
                centroid=Centroid(Collect(geo_expr)),
            )
            .order_by()
        )

        features = []
        total = 0
        for c in clusters:
            pt = c["centroid"]
            if pt is None:
                continue
            count = c["count"]
            total += count
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [pt.x, pt.y],
                    },
                    "properties": {
                        "cluster": True,
                        "point_count": count,
                    },
                }
            )

        response = Response(
            {
                "type": "FeatureCollection",
                "features": features,
                "total_count": total,
            }
        )
        if etag:
            response["ETag"] = etag
        return response


class PathwayGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.Pathway.objects.only(
        "id",
        "label",
        "pathway_type",
        "path",
    ).order_by("pk")
    serializer_class = PathwayGeoSerializer
    filterset_class = filters.PathwayFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class ConduitBankGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = (
        models.ConduitBank.objects.annotate(
            conduit_count=Count("conduits"),
        )
        .only(
            "id",
            "label",
            "pathway_type",
            "path",
            "configuration",
        )
        .order_by("pk")
    )
    serializer_class = ConduitBankGeoSerializer
    filterset_class = filters.ConduitBankFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class ConduitGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    # Exclude conduits that belong to a bank — those are represented by the bank line
    queryset = (
        models.Conduit.objects.filter(
            conduit_bank__isnull=True,
        )
        .only(
            "id",
            "label",
            "pathway_type",
            "path",
        )
        .order_by("pk")
    )
    serializer_class = ConduitGeoSerializer
    filterset_class = filters.ConduitFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class AerialSpanGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.AerialSpan.objects.only(
        "id",
        "label",
        "pathway_type",
        "path",
    ).order_by("pk")
    serializer_class = AerialSpanGeoSerializer
    filterset_class = filters.AerialSpanFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class DirectBuriedGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.DirectBuried.objects.only(
        "id",
        "label",
        "pathway_type",
        "path",
    ).order_by("pk")
    serializer_class = DirectBuriedGeoSerializer
    filterset_class = filters.DirectBuriedFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class CircuitGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.CircuitGeometry.objects.select_related(
        "circuit",
        "circuit__provider",
        "circuit__type",
    ).order_by("pk")
    serializer_class = CircuitGeoSerializer
    filterset_class = filters.CircuitGeometryFilterSet
    bbox_geo_field = "path"
    pagination_class = None
