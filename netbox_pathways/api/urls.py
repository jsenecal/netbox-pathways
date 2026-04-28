from django.urls import path
from netbox.api.routers import NetBoxRouter

from . import views
from .external_geo import ExternalLayerGeoView
from .geo import (
    AerialSpanGeoViewSet,
    CircuitGeoViewSet,
    ConduitBankGeoViewSet,
    ConduitGeoViewSet,
    DirectBuriedGeoViewSet,
    PathwayGeoViewSet,
    StructureGeoViewSet,
)
from .traversal import CableTraceView

router = NetBoxRouter()
router.register("structures", views.StructureViewSet)
router.register("conduit-banks", views.ConduitBankViewSet)
router.register("pathways", views.PathwayViewSet)
router.register("conduits", views.ConduitViewSet)
router.register("aerial-spans", views.AerialSpanViewSet)
router.register("direct-buried", views.DirectBuriedViewSet)
router.register("innerducts", views.InnerductViewSet)
router.register("junctions", views.ConduitJunctionViewSet)
router.register("pathway-locations", views.PathwayLocationViewSet)
router.register("cable-segments", views.CableSegmentViewSet)
router.register("site-geometries", views.SiteGeometryViewSet)
router.register("circuit-geometries", views.CircuitGeometryViewSet)
router.register("planned-routes", views.PlannedRouteViewSet)

# GeoJSON endpoints for QGIS / GIS client consumption
router.register("geo/structures", StructureGeoViewSet, basename="geo-structure")
router.register("geo/pathways", PathwayGeoViewSet, basename="geo-pathway")
router.register("geo/conduit-banks", ConduitBankGeoViewSet, basename="geo-conduitbank")
router.register("geo/conduits", ConduitGeoViewSet, basename="geo-conduit")
router.register("geo/aerial-spans", AerialSpanGeoViewSet, basename="geo-aerialspan")
router.register("geo/direct-buried", DirectBuriedGeoViewSet, basename="geo-directburied")
router.register("geo/circuits", CircuitGeoViewSet, basename="geo-circuit")

urlpatterns = router.urls + [
    # External plugin map layer endpoint
    path("geo/external/<str:layer_name>/", ExternalLayerGeoView.as_view(), name="external-geo"),
    # Graph traversal endpoints
    path("traversal/cable-trace/", CableTraceView.as_view(), name="traversal-cable-trace"),
]
