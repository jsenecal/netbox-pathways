from netbox.api.routers import NetBoxRouter

from . import views

router = NetBoxRouter()
router.register('structures', views.StructureViewSet)
router.register('conduit-banks', views.ConduitBankViewSet)
router.register('pathways', views.PathwayViewSet)
router.register('conduits', views.ConduitViewSet)
router.register('aerial-spans', views.AerialSpanViewSet)
router.register('direct-buried', views.DirectBuriedViewSet)
router.register('innerducts', views.InnerductViewSet)
router.register('junctions', views.ConduitJunctionViewSet)
router.register('cable-segments', views.CableSegmentViewSet)

urlpatterns = router.urls
