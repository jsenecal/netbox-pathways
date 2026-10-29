from django.urls import path
from netbox.api.routers import NetBoxRouter

from . import views
from .external_geo import ExternalLayerGeoView
from .geo import (
    CircuitGeoViewSet,
    MapInfoView,
    PathwayGeoViewSet,
    StructureGeoViewSet,
)
from .traversal import CableTraceView

router = NetBoxRouter()
router.register("structures", views.StructureViewSet)
router.register("pathways", views.PathwayViewSet)
router.register("junctions", views.ConduitJunctionViewSet)
router.register("pathway-locations", views.PathwayLocationViewSet)
router.register("cable-segments", views.CableSegmentViewSet)
router.register("site-geometries", views.SiteGeometryViewSet)
router.register("circuit-geometries", views.CircuitGeometryViewSet)
router.register("planned-routes", views.PlannedRouteViewSet)

# GeoJSON endpoints for QGIS / GIS client consumption
router.register("geo/structures", StructureGeoViewSet, basename="geo-structure")
router.register("geo/pathways", PathwayGeoViewSet, basename="geo-pathway")
router.register("geo/circuits", CircuitGeoViewSet, basename="geo-circuit")

urlpatterns = router.urls + [
    # Per-layer feature counts for the map (drives client-side gating)
    path("geo/info/", MapInfoView.as_view(), name="geo-info"),
    # External plugin map layer endpoint
    path("geo/external/<str:layer_name>/", ExternalLayerGeoView.as_view(), name="external-geo"),
    # Graph traversal endpoints
    path("traversal/cable-trace/", CableTraceView.as_view(), name="traversal-cable-trace"),
]
