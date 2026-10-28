"""OpenAPI schema generation for the GeoJSON API."""

from django.urls import include, path
from drf_spectacular.generators import SchemaGenerator

from netbox_pathways.api.urls import router


def test_geo_serializers_build_openapi_schema():
    """Regression: geo_field named the geo_4326 annotation, which drf-spectacular
    looked up as a model field, crashing the whole schema build with KeyError."""
    geo_routes = [p for p in router.urls if (p.name or "").startswith("geo-")]
    patterns = [path("api/plugins/pathways/", include(geo_routes))]
    schema = SchemaGenerator(patterns=patterns).get_schema(request=None, public=True)

    components = schema["components"]["schemas"]
    for name in ("StructureGeo", "PathwayGeo", "CircuitGeo"):
        assert "geometry" in components[name]["properties"], name
