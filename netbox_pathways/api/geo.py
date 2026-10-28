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

import django_filters
from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import Centroid, Length, SnapToGrid, Transform
from django.contrib.gis.geos import Polygon
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Case, CharField, Count, F, Max, OuterRef, Q, Subquery, Value, When
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_gis.fields import GeometryField
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .. import filtersets, models
from ..choices import PathwayStatusChoices, StructureStatusChoices
from ..geo import LEAFLET_SRID, get_srid
from ..pathway_types import DRAWN_TYPES_ORDERED

logger = logging.getLogger(__name__)

MAX_GEO_RESULTS = 2000


def _parse_bbox_wgs84(value):
    """Parse a ``west,south,east,north`` string into a WGS84 Polygon.

    Returns ``(polygon, [w, s, e, n])`` or ``(None, None)`` on invalid input.
    """
    if not value:
        return None, None
    try:
        west, south, east, north = (float(v) for v in value.split(","))
    except (ValueError, TypeError):
        return None, None
    poly = Polygon.from_bbox((west, south, east, north))
    poly.srid = LEAFLET_SRID
    return poly, [west, south, east, north]


def _parse_bbox(value):
    """Parse a ``west,south,east,north`` string into a WGS84 Polygon.

    Returns ``(polygon, [w, s, e, n])`` or ``(None, None)`` on invalid input.
    The polygon is already reprojected to the configured storage SRID, ready
    to use in an ``__intersects`` lookup.
    """
    poly, bounds = _parse_bbox_wgs84(value)
    if poly is not None and get_srid() != LEAFLET_SRID:
        poly.transform(get_srid())
    return poly, bounds


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


def _available_statuses():
    """Union of pathway and structure status choices, as {value, label, color} dicts.

    The two ChoiceSets ship identical but are independently overridable via
    FIELD_CHOICES, so merge by value (pathway order first).
    """
    merged = {}
    for choices in (PathwayStatusChoices, StructureStatusChoices):
        for value, label in choices:  # ChoiceSetMeta iterates normalized (value, label) pairs
            merged.setdefault(value, {"value": value, "label": str(label), "color": choices.colors.get(value)})
    return list(merged.values())


def _parse_exclude_status(request):
    """Statuses to hide, from ``?exclude_status=`` (repeated or comma-separated).

    Restricted to known status values so arbitrary input never reaches the
    query; unknown values are ignored. Returns a sorted list (stable ETag
    input).
    """
    requested = set()
    for raw in request.query_params.getlist("exclude_status"):
        requested.update(v.strip() for v in raw.split(","))
    known = {s["value"] for s in _available_statuses()}
    return sorted(requested & known)


def _exclude_status(qs, statuses):
    """Apply a status exclusion to ``qs`` if its model carries a status field."""
    if not statuses:
        return qs
    try:
        qs.model._meta.get_field("status")
    except FieldDoesNotExist:
        return qs
    return qs.exclude(status__in=statuses)


def _parse_occupied(request):
    """Tri-state ``?occupied=`` param: True, False, or None (absent/unrecognized).

    Mirrors the truthy/falsy spellings django-filter's BooleanFilter accepts so
    /info counts and the layer endpoints interpret the same request the same way.
    """
    raw = request.query_params.get("occupied")
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    return None


# --- GeoJSON Serializers ---
# geo_field is declared under the model's own geometry field name but sourced
# from the geo_4326 annotation (already WGS84).  The name must be a real model
# field: drf-spectacular looks it up on the model to type the geometry.
#
# NOTE: These serializers intentionally omit ``url`` (get_absolute_url).
# Calling reverse() per row is extremely expensive (~12 s / 1000 rows) due to
# lazy URL-pattern population.  The map client constructs detail URLs itself
# from featureType + id, so the field is not needed.


class StructureGeoSerializer(GeoFeatureModelSerializer):
    geometry = GeometryField(source="geo_4326", read_only=True)
    name = drf_serializers.CharField(read_only=True)
    site_name = drf_serializers.SerializerMethodField()

    class Meta:
        model = models.Structure
        geo_field = "geometry"
        fields = ["id", "name", "structure_type", "site_name"]

    def get_site_name(self, obj):
        return obj.site.name if obj.site_id else None


class PathwayGeoSerializer(GeoFeatureModelSerializer):
    geometry = GeometryField(source="geo_4326", read_only=True)
    geo_length = drf_serializers.FloatField(read_only=True)
    # Label of the descendant a ``?q=`` search matched, when the pathway was
    # found through one rather than on its own fields.
    search_match = drf_serializers.CharField(read_only=True, default=None)

    class Meta:
        model = models.Pathway
        geo_field = "geometry"
        fields = ["id", "label", "pathway_type", "geo_length", "start_anchor", "end_anchor", "search_match"]


class CircuitGeoSerializer(GeoFeatureModelSerializer):
    path = GeometryField(source="geo_4326", read_only=True)
    cid = drf_serializers.CharField(source="circuit.cid", read_only=True)
    provider = drf_serializers.CharField(source="circuit.provider.name", read_only=True)
    circuit_type = drf_serializers.CharField(source="circuit.type.name", read_only=True)
    status = drf_serializers.CharField(source="circuit.status", read_only=True)

    class Meta:
        model = models.CircuitGeometry
        geo_field = "path"
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

    bbox_geo_field = "geometry"  # native geometry column name

    def _apply_bbox(self, qs):
        """Annotate geo_4326 and apply bbox filter (no result cap)."""
        qs = qs.annotate(geo_4326=Transform(self.bbox_geo_field, LEAFLET_SRID))
        poly, _ = _parse_bbox(self.request.query_params.get("bbox"))
        if poly is not None:
            qs = qs.filter(**{f"{self.bbox_geo_field}__intersects": poly})
        return qs

    def get_queryset(self):
        # Enforce NetBox object-level permissions: without this, any user
        # holding a constrained view permission on the model would receive
        # every row, leaking other tenants' plant data through the map.
        qs = super().get_queryset().restrict(self.request.user, "view")
        qs = _exclude_status(qs, _parse_exclude_status(self.request))
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


# --- Map filterset ---


class PathwayGeoFilterSet(filtersets.PathwayFilterSet):
    """The pathway filters, plus what the map needs to draw containers only.

    ``?containers=true`` keeps the pathways the map draws (see
    ``PathwayQuerySet.map_containers``); ``false`` keeps everything else.
    ``?q=`` also matches a pathway through any descendant that matches,
    since a search for an undrawn child must land on its container.
    """

    containers = django_filters.BooleanFilter(method="filter_containers", label="Map containers only")

    class Meta(filtersets.PathwayFilterSet.Meta):
        pass

    def filter_containers(self, queryset, name, value):
        containers = queryset.map_containers()
        return containers if value else queryset.exclude(pk__in=containers.values("pk"))

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        own = super().search(queryset, name, value).values("pk")
        # Restricted, so a search cannot probe labels the user may not view
        children = super().search(models.Pathway.objects.restrict(self.request.user, "view"), name, value)
        child_match = Subquery(
            children.filter(path__descendant=OuterRef("path")).order_by("label", "pk").values("label")[:1]
        )
        return queryset.annotate(
            search_match=Case(When(pk__in=own, then=Value(None)), default=child_match, output_field=CharField())
        ).filter(Q(pk__in=own) | Q(search_match__isnull=False))


# --- GeoJSON ViewSets (read-only, unpaginated) ---


class StructureGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = (
        models.Structure.objects.select_related("site")
        .only(
            "id",
            "name",
            "structure_type",
            "geometry",
            "site__name",
        )
        .order_by("pk")
    )
    serializer_class = StructureGeoSerializer
    filterset_class = filtersets.StructureFilterSet
    bbox_geo_field = "geometry"
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
                return self._clustered_response(qs, zoom, etag)
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

    def _clustered_response(self, qs, zoom, etag=None):
        # ``qs`` is the same filtered queryset the plain branch serializes
        # (bbox, status exclusion, and filterset params such as ``occupied``
        # all applied), so cluster counts always agree with the points the
        # client gets after zooming in. Aggregation ignores the result cap.
        grid_size = _grid_size_for_zoom(zoom)
        geo_expr = Transform("geometry", LEAFLET_SRID)
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
        models.Pathway.objects.filter(geometry__isnull=False)
        .only(
            "id",
            "label",
            "pathway_type",
            "geometry",
        )
        .annotate(_geo_length=Length("geometry"))
        .order_by("pk")
    )
    serializer_class = PathwayGeoSerializer
    filterset_class = PathwayGeoFilterSet
    bbox_geo_field = "geometry"
    pagination_class = None


class CircuitGeoViewSet(BboxFilterMixin, ReadOnlyModelViewSet):
    queryset = models.CircuitGeometry.objects.select_related(
        "circuit",
        "circuit__provider",
        "circuit__type",
    ).order_by("pk")
    serializer_class = CircuitGeoSerializer
    filterset_class = filtersets.CircuitGeometryFilterSet
    bbox_geo_field = "path"
    pagination_class = None


# --- /info endpoint ---


# The /info key of each drawn pathway type's map layer.
PATHWAY_LAYER_KEYS = {
    "conduit_bank": "conduit_banks",
    "conduit": "conduits",
    "aerial": "aerial_spans",
    "direct_buried": "direct_buried",
    "submarine": "submarine",
}


def _info_layers(user):
    """Layers reported by /info as ``(response_key, queryset, geo_field)``.

    Restricted with the same object permissions the layer endpoints apply,
    so counts never disclose rows the user cannot see. A pathway layer counts
    only map containers of its type, so a banked conduit is not counted with
    its bank.
    """
    pathways = models.Pathway.objects.restrict(user, "view").map_containers()
    return (
        ("structures", models.Structure.objects.restrict(user, "view"), "geometry"),
        *((PATHWAY_LAYER_KEYS[t], pathways.filter(pathway_type=t), "geometry") for t in DRAWN_TYPES_ORDERED),
        ("circuits", models.CircuitGeometry.objects.restrict(user, "view"), "path"),
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
    "submarine": {"hide": 500},
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
        excluded_statuses = _parse_exclude_status(request)
        occupied = _parse_occupied(request)

        counts = {}
        thresholds = _resolved_thresholds()
        external_counts = {}
        external_thresholds = {}

        max_updated = None
        total = 0

        def _count(qs, geo):
            nonlocal max_updated, total
            if bbox_poly is not None:
                qs = qs.annotate(_pw_geo=geo).filter(_pw_geo__intersects=bbox_poly)
            t, c = _etag_components(qs)
            total += c
            if t and (max_updated is None or t > max_updated):
                max_updated = t
            return c

        for key, qs, geo_field in _info_layers(request.user):
            qs = _exclude_status(qs, excluded_statuses)
            qs = filtersets.apply_occupied(qs, occupied)
            counts[key] = _count(qs, F(geo_field))

        from .external_geo import resolve_geometry_expression

        for layer_reg in _external_reference_layers():
            try:
                qs = layer_reg.queryset(request)
                geo_expr = resolve_geometry_expression(qs.model, layer_reg.geometry_field)
            except Exception:
                logger.warning(
                    "Skipping external layer '%s' in /info: invalid registration", layer_reg.name, exc_info=True
                )
                continue
            external_counts[layer_reg.name] = _count(qs, geo_expr)
            external_thresholds[layer_reg.name] = {"hide": layer_reg.max_features}

        if external_counts:
            counts["external"] = external_counts
            thresholds["external"] = external_thresholds

        etag = hashlib.md5(
            f"{max_updated}:{total}:{bbox_list}:{excluded_statuses}:{occupied}".encode(),
            usedforsecurity=False,
        ).hexdigest()
        if request.META.get("HTTP_IF_NONE_MATCH") == etag:
            return Response(status=304, headers={"ETag": etag})

        response = Response(
            {
                "bbox": bbox_list,
                "counts": counts,
                "thresholds": thresholds,
                "statuses": _available_statuses(),
            }
        )
        response["ETag"] = etag
        return response
