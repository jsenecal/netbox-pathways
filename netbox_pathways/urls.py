from django.urls import include, path
from utilities.urls import get_model_urls

from . import views

urlpatterns = [
    # Structures
    path('structures/', views.StructureListView.as_view(), name='structure_list'),
    path('structures/add/', views.StructureEditView.as_view(), name='structure_add'),
    path('structures/import/', views.StructureBulkImportView.as_view(), name='structure_import'),
    path('structures/edit/', views.StructureBulkEditView.as_view(), name='structure_bulk_edit'),
    path('structures/delete/', views.StructureBulkDeleteView.as_view(), name='structure_bulk_delete'),
    path('structures/<int:pk>/', include([
        path('', views.StructureView.as_view(), name='structure'),
        path('edit/', views.StructureEditView.as_view(), name='structure_edit'),
        path('create-site/', views.StructureCreateSiteView.as_view(), name='structure_create_site'),
        path('delete/', views.StructureDeleteView.as_view(), name='structure_delete'),
        *get_model_urls('netbox_pathways', 'structure'),
    ])),

    # Pathways (all types)
    path('pathways/', views.PathwayListView.as_view(), name='pathway_list'),
    path('pathways/<int:pk>/', include([
        path('', views.PathwayView.as_view(), name='pathway'),
        *get_model_urls('netbox_pathways', 'pathway'),
    ])),

    # Conduits
    path('conduits/', views.ConduitListView.as_view(), name='conduit_list'),
    path('conduits/add/', views.ConduitEditView.as_view(), name='conduit_add'),
    path('conduits/import/', views.ConduitBulkImportView.as_view(), name='conduit_import'),
    path('conduits/edit/', views.ConduitBulkEditView.as_view(), name='conduit_bulk_edit'),
    path('conduits/delete/', views.ConduitBulkDeleteView.as_view(), name='conduit_bulk_delete'),
    path('conduits/<int:pk>/', include([
        path('', views.ConduitView.as_view(), name='conduit'),
        path('edit/', views.ConduitEditView.as_view(), name='conduit_edit'),
        path('delete/', views.ConduitDeleteView.as_view(), name='conduit_delete'),
        *get_model_urls('netbox_pathways', 'conduit'),
    ])),

    # Aerial Spans
    path('aerial-spans/', views.AerialSpanListView.as_view(), name='aerialspan_list'),
    path('aerial-spans/add/', views.AerialSpanEditView.as_view(), name='aerialspan_add'),
    path('aerial-spans/import/', views.AerialSpanBulkImportView.as_view(), name='aerialspan_import'),
    path('aerial-spans/edit/', views.AerialSpanBulkEditView.as_view(), name='aerialspan_bulk_edit'),
    path('aerial-spans/delete/', views.AerialSpanBulkDeleteView.as_view(), name='aerialspan_bulk_delete'),
    path('aerial-spans/<int:pk>/', include([
        path('', views.AerialSpanView.as_view(), name='aerialspan'),
        path('edit/', views.AerialSpanEditView.as_view(), name='aerialspan_edit'),
        path('delete/', views.AerialSpanDeleteView.as_view(), name='aerialspan_delete'),
        *get_model_urls('netbox_pathways', 'aerialspan'),
    ])),

    # Direct Buried
    path('direct-buried/', views.DirectBuriedListView.as_view(), name='directburied_list'),
    path('direct-buried/add/', views.DirectBuriedEditView.as_view(), name='directburied_add'),
    path('direct-buried/edit/', views.DirectBuriedBulkEditView.as_view(), name='directburied_bulk_edit'),
    path('direct-buried/delete/', views.DirectBuriedBulkDeleteView.as_view(), name='directburied_bulk_delete'),
    path('direct-buried/<int:pk>/', include([
        path('', views.DirectBuriedView.as_view(), name='directburied'),
        path('edit/', views.DirectBuriedEditView.as_view(), name='directburied_edit'),
        path('delete/', views.DirectBuriedDeleteView.as_view(), name='directburied_delete'),
        *get_model_urls('netbox_pathways', 'directburied'),
    ])),

    # Innerducts
    path('innerducts/', views.InnerductListView.as_view(), name='innerduct_list'),
    path('innerducts/add/', views.InnerductEditView.as_view(), name='innerduct_add'),
    path('innerducts/edit/', views.InnerductBulkEditView.as_view(), name='innerduct_bulk_edit'),
    path('innerducts/delete/', views.InnerductBulkDeleteView.as_view(), name='innerduct_bulk_delete'),
    path('innerducts/<int:pk>/', include([
        path('', views.InnerductView.as_view(), name='innerduct'),
        path('edit/', views.InnerductEditView.as_view(), name='innerduct_edit'),
        path('delete/', views.InnerductDeleteView.as_view(), name='innerduct_delete'),
        *get_model_urls('netbox_pathways', 'innerduct'),
    ])),

    # Conduit Banks
    path('conduit-banks/', views.ConduitBankListView.as_view(), name='conduitbank_list'),
    path('conduit-banks/add/', views.ConduitBankEditView.as_view(), name='conduitbank_add'),
    path('conduit-banks/import/', views.ConduitBankBulkImportView.as_view(), name='conduitbank_import'),
    path('conduit-banks/edit/', views.ConduitBankBulkEditView.as_view(), name='conduitbank_bulk_edit'),
    path('conduit-banks/delete/', views.ConduitBankBulkDeleteView.as_view(), name='conduitbank_bulk_delete'),
    path('conduit-banks/<int:pk>/', include([
        path('', views.ConduitBankView.as_view(), name='conduitbank'),
        path('edit/', views.ConduitBankEditView.as_view(), name='conduitbank_edit'),
        path('delete/', views.ConduitBankDeleteView.as_view(), name='conduitbank_delete'),
        *get_model_urls('netbox_pathways', 'conduitbank'),
    ])),

    # Conduit Junctions
    path('junctions/', views.ConduitJunctionListView.as_view(), name='conduitjunction_list'),
    path('junctions/add/', views.ConduitJunctionEditView.as_view(), name='conduitjunction_add'),
    path('junctions/<int:pk>/', include([
        path('', views.ConduitJunctionView.as_view(), name='conduitjunction'),
        path('edit/', views.ConduitJunctionEditView.as_view(), name='conduitjunction_edit'),
        path('delete/', views.ConduitJunctionDeleteView.as_view(), name='conduitjunction_delete'),
        *get_model_urls('netbox_pathways', 'conduitjunction'),
    ])),

    # Pathway Locations (waypoints)
    path('pathway-locations/', views.PathwayLocationListView.as_view(), name='pathwaylocation_list'),
    path('pathway-locations/add/', views.PathwayLocationEditView.as_view(), name='pathwaylocation_add'),
    path('pathway-locations/<int:pk>/', include([
        path('', views.PathwayLocationView.as_view(), name='pathwaylocation'),
        path('edit/', views.PathwayLocationEditView.as_view(), name='pathwaylocation_edit'),
        path('delete/', views.PathwayLocationDeleteView.as_view(), name='pathwaylocation_delete'),
        *get_model_urls('netbox_pathways', 'pathwaylocation'),
    ])),

    # Cable Segments
    path('cable-segments/', views.CableSegmentListView.as_view(), name='cablesegment_list'),
    path('cable-segments/add/', views.CableSegmentEditView.as_view(), name='cablesegment_add'),
    path('cable-segments/import/', views.CableSegmentBulkImportView.as_view(), name='cablesegment_import'),
    path('cable-segments/edit/', views.CableSegmentBulkEditView.as_view(), name='cablesegment_bulk_edit'),
    path('cable-segments/delete/', views.CableSegmentBulkDeleteView.as_view(), name='cablesegment_bulk_delete'),
    path('cable-segments/<int:pk>/', include([
        path('', views.CableSegmentView.as_view(), name='cablesegment'),
        path('edit/', views.CableSegmentEditView.as_view(), name='cablesegment_edit'),
        path('delete/', views.CableSegmentDeleteView.as_view(), name='cablesegment_delete'),
        *get_model_urls('netbox_pathways', 'cablesegment'),
    ])),

    # Slack Loops
    path('slack-loops/', views.SlackLoopListView.as_view(), name='slackloop_list'),
    path('slack-loops/add/', views.SlackLoopEditView.as_view(), name='slackloop_add'),
    path('slack-loops/edit/', views.SlackLoopBulkEditView.as_view(), name='slackloop_bulk_edit'),
    path('slack-loops/delete/', views.SlackLoopBulkDeleteView.as_view(), name='slackloop_bulk_delete'),
    path('slack-loops/<int:pk>/', include([
        path('', views.SlackLoopView.as_view(), name='slackloop'),
        path('edit/', views.SlackLoopEditView.as_view(), name='slackloop_edit'),
        path('delete/', views.SlackLoopDeleteView.as_view(), name='slackloop_delete'),
        *get_model_urls('netbox_pathways', 'slackloop'),
    ])),

    # Site Geometries
    path('site-geometries/', views.SiteGeometryListView.as_view(), name='sitegeometry_list'),
    path('site-geometries/add/', views.SiteGeometryEditView.as_view(), name='sitegeometry_add'),
    path('site-geometries/<int:pk>/', include([
        path('', views.SiteGeometryView.as_view(), name='sitegeometry'),
        path('edit/', views.SiteGeometryEditView.as_view(), name='sitegeometry_edit'),
        path('delete/', views.SiteGeometryDeleteView.as_view(), name='sitegeometry_delete'),
        *get_model_urls('netbox_pathways', 'sitegeometry'),
    ])),

    # Circuit Geometries
    path('circuit-geometries/', views.CircuitGeometryListView.as_view(), name='circuitgeometry_list'),
    path('circuit-geometries/add/', views.CircuitGeometryEditView.as_view(), name='circuitgeometry_add'),
    path('circuit-geometries/<int:pk>/', include([
        path('', views.CircuitGeometryView.as_view(), name='circuitgeometry'),
        path('edit/', views.CircuitGeometryEditView.as_view(), name='circuitgeometry_edit'),
        path('delete/', views.CircuitGeometryDeleteView.as_view(), name='circuitgeometry_delete'),
        *get_model_urls('netbox_pathways', 'circuitgeometry'),
    ])),

    # Planned Routes
    path('planned-routes/', views.PlannedRouteListView.as_view(), name='plannedroute_list'),
    path('planned-routes/add/', views.PlannedRouteEditView.as_view(), name='plannedroute_add'),
    path('planned-routes/edit/', views.PlannedRouteBulkEditView.as_view(), name='plannedroute_bulk_edit'),
    path('planned-routes/delete/', views.PlannedRouteBulkDeleteView.as_view(), name='plannedroute_bulk_delete'),
    path('planned-routes/<int:pk>/', include([
        path('', views.PlannedRouteView.as_view(), name='plannedroute'),
        path('edit/', views.PlannedRouteEditView.as_view(), name='plannedroute_edit'),
        path('delete/', views.PlannedRouteDeleteView.as_view(), name='plannedroute_delete'),
        path('split/', views.PlannedRouteSplitView.as_view(), name='plannedroute_split'),
        path('revert/', views.PlannedRouteRevertSplitView.as_view(), name='plannedroute_revert'),
        path('apply/', views.PlannedRouteApplyView.as_view(), name='plannedroute_apply'),
        *get_model_urls('netbox_pathways', 'plannedroute'),
    ])),

    # Route Planner
    path('route-planner/', views.RoutePlannerView.as_view(), name='route_planner'),
    path('route-planner/find/', views.RoutePlannerFindView.as_view(), name='route_planner_find'),
    path('route-planner/save/', views.RoutePlannerSaveView.as_view(), name='route_planner_save'),
    path('route-planner/constraint/', views.RoutePlannerConstraintView.as_view(), name='route_planner_constraint'),

    # Pull Sheets
    path('pull-sheets/', views.PullSheetListView.as_view(), name='pullsheet_list'),
    path('pull-sheets/<int:cable_pk>/', views.PullSheetDetailView.as_view(), name='pullsheet_detail'),

    # Map
    path('map/', views.MapView.as_view(), name='map'),

    # Adjacency API for pathway filtering
    path('adjacency/', views.AdjacencyView.as_view(), name='adjacency'),

    # Cable routing panel HTMX endpoints
    path('cable-routing/<int:cable_pk>/add-segment/', views.CableRoutingAddSegmentView.as_view(), name='cable_routing_add'),
    path('cable-routing/<int:cable_pk>/delete-segment/<int:segment_pk>/', views.CableRoutingDeleteSegmentView.as_view(), name='cable_routing_delete'),
    path('cable-routing/<int:cable_pk>/find-route/', views.CableRoutingFindRouteView.as_view(), name='cable_routing_find'),
    path('cable-routing/<int:cable_pk>/apply-route/', views.CableRoutingApplyRouteView.as_view(), name='cable_routing_apply'),
    path('cable-routing/<int:cable_pk>/table/', views.CableRoutingTableView.as_view(), name='cable_routing_table'),
]
