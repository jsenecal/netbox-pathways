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
import logging

from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import Centroid, Length, SnapToGrid, Transform
from django.contrib.gis.geos import Polygon
from django.db.models import Count, Max
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filters, models
from ..geo import LEAFLET_SRID, get_srid

logger = logging.getLogger(__name__)

MAX_GEO_RESULTS = 2000


def _parse_bbox(value):
    """Parse a ``west,south,east,north`` string into a WGS84 Polygon.

    Returns ``(polygon, [w, s, e, n])`` or ``(None, None)`` on invalid input.
    The polygon is already reprojected to the configured storage SRID, ready
    to use in an ``__intersects`` lookup.
    """
    if not value:
        return None, None
    try:
        west, south, east, north = (float(v) for v in value.split(","))
    except (ValueError, TypeError):
        return None, None
    poly = Polygon.from_bbox((west, south, east, north))
    poly.srid = LEAFLET_SRID
    if get_srid() != LEAFLET_SRID:
        poly.transform(get_srid())
    return poly, [west, south, east, north]


def _etag_components(queryset):
    """Return ``(max_last_updated, count)`` for a queryset.

    Shared between the list ViewSets and ``MapInfoView`` so the ETag hash
    inputs stay consistent across endpoints.
    """
    agg = queryset.aggregate(t=Max("last_updated"), c=Count("id"))
    return agg["t"], agg["c"] or 0


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
    geo_length = drf_serializers.FloatField(read_only=True)

    class Meta:
        model = models.Pathway
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type", "geo_length"]


class ConduitBankGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    conduit_count = drf_serializers.IntegerField(read_only=True)
    geo_length = drf_serializers.FloatField(read_only=True)

    class Meta:
        model = models.ConduitBank
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type", "configuration", "conduit_count", "geo_length"]


class ConduitGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    geo_length = drf_serializers.FloatField(read_only=True)

    class Meta:
        model = models.Conduit
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type", "geo_length"]


class AerialSpanGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    geo_length = drf_serializers.FloatField(read_only=True)

    class Meta:
        model = models.AerialSpan
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type", "geo_length"]


class DirectBuriedGeoSerializer(GeoFeatureModelSerializer):
    geo_4326 = GeometryField(read_only=True)
    geo_length = drf_serializers.FloatField(read_only=True)

    class Meta:
        model = models.DirectBuried
        geo_field = "geo_4326"
        fields = ["id", "label", "pathway_type", "geo_length"]


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
        poly, _ = _parse_bbox(self.request.query_params.get("bbox"))
        if poly is not None:
            qs = qs.filter(**{f"{self.bbox_geo_field}__intersects": poly})
        return qs

    def get_queryset(self):
        qs = super().get_queryset()
        return self._apply_bbox(qs)

    def _etag_for_queryset(self, queryset):
        """Lightweight ETag from max(last_updated) + count."""
        t, c = _etag_components(queryset)
        return hashlib.md5(f"{t}:{c}".encode(), usedforsecurity=False).hexdigest()

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
    # Indoor (location-to-location) pathways have no path and cannot be mapped
    queryset = (
        models.Pathway.objects.filter(path__isnull=False)
        .only(
            "id",
            "label",
            "pathway_type",
            "path",
        )
        .annotate(_geo_length=Length("path"))
        .order_by("pk")
    )
    serializer_class = PathwayGeoSerializer
    filterset_class = filters.PathwayFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class ConduitBankGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = (
        models.ConduitBank.objects.filter(path__isnull=False)
        .annotate(
            conduit_count=Count("conduits"),
            _geo_length=Length("path"),
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
    # Exclude conduits that belong to a bank -- those are represented by the bank line
    queryset = (
        models.Conduit.objects.filter(
            conduit_bank__isnull=True,
            path__isnull=False,
        )
        .annotate(_geo_length=Length("path"))
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
    queryset = (
        models.AerialSpan.objects.filter(path__isnull=False)
        .only(
            "id",
            "label",
            "pathway_type",
            "path",
        )
        .annotate(_geo_length=Length("path"))
        .order_by("pk")
    )
    serializer_class = AerialSpanGeoSerializer
    filterset_class = filters.AerialSpanFilterSet
    bbox_geo_field = "path"
    pagination_class = None


class DirectBuriedGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = (
        models.DirectBuried.objects.filter(path__isnull=False)
        .only(
            "id",
            "label",
            "pathway_type",
            "path",
        )
        .annotate(_geo_length=Length("path"))
        .order_by("pk")
    )
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


# --- /info endpoint ---


# Layers reported by /info. Each entry: (response_key, model, geo_field, extra_filter).
# ``extra_filter`` is an optional Q-style filter dict applied before counting,
# mirroring the corresponding GeoJSON viewset's queryset constraints (so e.g.
# banked conduits aren't double-counted between "conduits" and "conduit_banks").
_INFO_LAYERS = (
    ("structures", models.Structure, "location", None),
    ("conduit_banks", models.ConduitBank, "path", None),
    ("conduits", models.Conduit, "path", {"conduit_bank__isnull": True}),
    ("aerial_spans", models.AerialSpan, "path", None),
    ("direct_buried", models.DirectBuried, "path", None),
    ("circuits", models.CircuitGeometry, "path", None),
)


# Per-layer thresholds the frontend uses to gate rendering. ``cluster`` (when
# present) is the count above which client-side clustering switches on;
# ``hide`` is the count above which the layer is skipped entirely and its
# toggle dimmed. Admins override with PLUGINS_CONFIG['netbox_pathways']
# ['map_thresholds'][<layer_key>] = {...} -- shallow per-layer merge.
DEFAULT_MAP_THRESHOLDS = {
    "structures": {"cluster": 200, "hide": 5000},
    "conduit_banks": {"hide": 500},
    "conduits": {"hide": 500},
    "aerial_spans": {"hide": 500},
    "direct_buried": {"hide": 500},
    "circuits": {"hide": 500},
}


def _resolved_thresholds():
    """Merge plugin defaults with PLUGINS_CONFIG overrides (per-layer shallow merge)."""
    from django.conf import settings

    overrides = (
        settings.PLUGINS_CONFIG.get("netbox_pathways", {}).get("map_thresholds", {})
        if hasattr(settings, "PLUGINS_CONFIG")
        else {}
    )
    return {key: overrides.get(key, default) for key, default in DEFAULT_MAP_THRESHOLDS.items()}


def _external_reference_layers():
    """Return reference-mode external layer registrations (URL-mode skipped)."""
    from ..registry import registry

    return [lr for lr in registry.all() if lr.source == "reference"]


class MapInfoView(APIView):
    """Return per-layer feature counts and thresholds for an optional bbox.

    Drives the map frontend's per-layer gating: render plain, client-cluster,
    or hide. Counts are computed once with a shared bbox intersection;
    thresholds come from plugin defaults overridable via PLUGINS_CONFIG.
    Reference-mode external layers participate; URL-mode external layers
    cannot be counted server-side and are intentionally omitted.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        bbox_poly, bbox_list = _parse_bbox(request.query_params.get("bbox"))

        counts = {}
        thresholds = _resolved_thresholds()
        external_counts = {}
        external_thresholds = {}

        max_updated = None
        total = 0

        def _count(qs, geo_field):
            nonlocal max_updated, total
            if bbox_poly is not None:
                qs = qs.filter(**{f"{geo_field}__intersects": bbox_poly})
            t, c = _etag_components(qs)
            total += c
            if t and (max_updated is None or t > max_updated):
                max_updated = t
            return c

        for key, model, geo_field, extra_filter in _INFO_LAYERS:
            qs = model.objects.all()
            if extra_filter:
                qs = qs.filter(**extra_filter)
            counts[key] = _count(qs, geo_field)

        from .external_geo import _resolve_geo_column

        for layer_reg in _external_reference_layers():
            try:
                qs = layer_reg.queryset(request)
                geo_path, _ = _resolve_geo_column(qs.model, layer_reg.geometry_field)
            except Exception:
                logger.warning(
                    "Skipping external layer '%s' in /info: invalid registration", layer_reg.name, exc_info=True
                )
                continue
            external_counts[layer_reg.name] = _count(qs, geo_path)
            external_thresholds[layer_reg.name] = {"hide": layer_reg.max_features}

        if external_counts:
            counts["external"] = external_counts
            thresholds["external"] = external_thresholds

        etag = hashlib.md5(
            f"{max_updated}:{total}:{bbox_list}".encode(),
            usedforsecurity=False,
        ).hexdigest()
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=304, headers={"ETag": etag})

        response = Response({"bbox": bbox_list, "counts": counts, "thresholds": thresholds})
        response["ETag"] = etag
        return response
