"""GeoJSON endpoint for reference-mode external map layers.

Resolves geometry by joining through the FK declared in the layer
registration, transforms to WGS84, applies bbox filtering, and returns
a standard GeoJSON FeatureCollection.
"""

from __future__ import annotations

import logging

from django.contrib.gis.db import models as gis_models
from django.contrib.gis.db.models.functions import Transform
from django.contrib.gis.geos import Polygon
from django.db import models as db_models
from django.http import Http404, JsonResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from netbox_pathways.api.geo import MAX_GEO_RESULTS
from netbox_pathways.geo import LEAFLET_SRID
from netbox_pathways.registry import SUPPORTED_GEO_MODELS, registry

logger = logging.getLogger(__name__)


def _resolve_geo_column(model, geometry_field: str) -> tuple[str, str]:
    """Return (fk_field__geo_column, target_model_label) for the FK.

    Raises ValueError if the FK target is not in SUPPORTED_GEO_MODELS.
    """
    fk = model._meta.get_field(geometry_field)
    target = fk.related_model
    target_label = f"{target._meta.app_label}.{target._meta.model_name}"
    # Case-insensitive lookup to tolerate label casing
    for supported_label, geo_col in SUPPORTED_GEO_MODELS.items():
        if supported_label.lower() == target_label.lower():
            return f"{geometry_field}__{geo_col}", supported_label
    raise ValueError(
        f"FK '{geometry_field}' on {model.__name__} points to {target_label}, which is not in SUPPORTED_GEO_MODELS."
    )


def _build_properties(obj, feature_fields: list[str] | None, model) -> dict:
    """Build GeoJSON properties dict from model instance."""
    props: dict = {"id": obj.pk}

    if feature_fields is not None:
        fields_to_use = feature_fields
    else:
        # Auto-detect scalar fields + FK display values
        fields_to_use = []
        for f in model._meta.get_fields():
            if not hasattr(f, "column"):
                continue  # skip reverse relations, M2M, etc.
            if f.name in ("id", "pk"):
                continue  # already handled above
            if isinstance(f, gis_models.GeometryField):
                continue  # skip geometry fields
            if isinstance(f, (db_models.BinaryField, db_models.JSONField)):
                continue  # skip non-serializable / large fields
            fields_to_use.append(f.name)

    for fname in fields_to_use:
        val = getattr(obj, fname, None)
        # FK → use __str__ of related object
        if hasattr(val, "pk"):
            props[fname] = str(val)
        elif val is not None:
            props[fname] = val
        else:
            props[fname] = None
    return props


class ExternalLayerGeoView(APIView):
    """Serve GeoJSON for a reference-mode registered layer."""

    permission_classes = [IsAuthenticated]

    def get(self, request, layer_name: str):
        layer_reg = registry.get(layer_name)
        if layer_reg is None or layer_reg.source != "reference":
            raise Http404(f"No reference-mode layer named '{layer_name}'.")

        qs = layer_reg.queryset(request)
        model = qs.model

        fk_geo_path, _target_label = _resolve_geo_column(
            model,
            layer_reg.geometry_field,
        )

        # Annotate with WGS84 geometry
        qs = qs.annotate(
            _geo_4326=Transform(fk_geo_path, LEAFLET_SRID),
        ).exclude(_geo_4326__isnull=True)

        # Bbox filtering
        bbox_str = request.query_params.get("bbox", "")
        if bbox_str:
            try:
                w, s, e, n = (float(x) for x in bbox_str.split(","))
                bbox_poly = Polygon.from_bbox((w, s, e, n))
                bbox_poly.srid = LEAFLET_SRID
                qs = qs.filter(_geo_4326__intersects=bbox_poly)
            except (ValueError, TypeError):
                pass  # ignore malformed bbox

        qs = qs[:MAX_GEO_RESULTS]

        features = []
        for obj in qs:
            geom = obj._geo_4326
            if geom is None:
                continue
            props = _build_properties(obj, layer_reg.feature_fields, model)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": geom.geom_type,
                        "coordinates": geom.coords,
                    },
                    "properties": props,
                }
            )

        return JsonResponse(
            {
                "type": "FeatureCollection",
                "features": features,
            }
        )
