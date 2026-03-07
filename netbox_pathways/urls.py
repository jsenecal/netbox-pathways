from django.urls import path

from . import views

urlpatterns = [
    # Structures
    path('structures/', views.StructureListView.as_view(), name='structure_list'),
    path('structures/add/', views.StructureEditView.as_view(), name='structure_add'),
    path('structures/import/', views.StructureBulkImportView.as_view(), name='structure_import'),
    path('structures/edit/', views.StructureBulkEditView.as_view(), name='structure_bulk_edit'),
    path('structures/delete/', views.StructureBulkDeleteView.as_view(), name='structure_bulk_delete'),
    path('structures/<int:pk>/', views.StructureView.as_view(), name='structure'),
    path('structures/<int:pk>/edit/', views.StructureEditView.as_view(), name='structure_edit'),
    path('structures/<int:pk>/delete/', views.StructureDeleteView.as_view(), name='structure_delete'),

    # Pathways (all types)
    path('pathways/', views.PathwayListView.as_view(), name='pathway_list'),
    path('pathways/<int:pk>/', views.PathwayView.as_view(), name='pathway'),

    # Conduits
    path('conduits/', views.ConduitListView.as_view(), name='conduit_list'),
    path('conduits/add/', views.ConduitEditView.as_view(), name='conduit_add'),
    path('conduits/import/', views.ConduitBulkImportView.as_view(), name='conduit_import'),
    path('conduits/edit/', views.ConduitBulkEditView.as_view(), name='conduit_bulk_edit'),
    path('conduits/delete/', views.ConduitBulkDeleteView.as_view(), name='conduit_bulk_delete'),
    path('conduits/<int:pk>/', views.ConduitView.as_view(), name='conduit'),
    path('conduits/<int:pk>/edit/', views.ConduitEditView.as_view(), name='conduit_edit'),
    path('conduits/<int:pk>/delete/', views.ConduitDeleteView.as_view(), name='conduit_delete'),

    # Aerial Spans
    path('aerial-spans/', views.AerialSpanListView.as_view(), name='aerialspan_list'),
    path('aerial-spans/add/', views.AerialSpanEditView.as_view(), name='aerialspan_add'),
    path('aerial-spans/import/', views.AerialSpanBulkImportView.as_view(), name='aerialspan_import'),
    path('aerial-spans/edit/', views.AerialSpanBulkEditView.as_view(), name='aerialspan_bulk_edit'),
    path('aerial-spans/delete/', views.AerialSpanBulkDeleteView.as_view(), name='aerialspan_bulk_delete'),
    path('aerial-spans/<int:pk>/', views.AerialSpanView.as_view(), name='aerialspan'),
    path('aerial-spans/<int:pk>/edit/', views.AerialSpanEditView.as_view(), name='aerialspan_edit'),
    path('aerial-spans/<int:pk>/delete/', views.AerialSpanDeleteView.as_view(), name='aerialspan_delete'),

    # Direct Buried
    path('direct-buried/', views.DirectBuriedListView.as_view(), name='directburied_list'),
    path('direct-buried/add/', views.DirectBuriedEditView.as_view(), name='directburied_add'),
    path('direct-buried/<int:pk>/', views.DirectBuriedView.as_view(), name='directburied'),
    path('direct-buried/<int:pk>/edit/', views.DirectBuriedEditView.as_view(), name='directburied_edit'),
    path('direct-buried/<int:pk>/delete/', views.DirectBuriedDeleteView.as_view(), name='directburied_delete'),

    # Innerducts
    path('innerducts/', views.InnerductListView.as_view(), name='innerduct_list'),
    path('innerducts/add/', views.InnerductEditView.as_view(), name='innerduct_add'),
    path('innerducts/<int:pk>/', views.InnerductView.as_view(), name='innerduct'),
    path('innerducts/<int:pk>/edit/', views.InnerductEditView.as_view(), name='innerduct_edit'),
    path('innerducts/<int:pk>/delete/', views.InnerductDeleteView.as_view(), name='innerduct_delete'),

    # Conduit Banks
    path('conduit-banks/', views.ConduitBankListView.as_view(), name='conduitbank_list'),
    path('conduit-banks/add/', views.ConduitBankEditView.as_view(), name='conduitbank_add'),
    path('conduit-banks/import/', views.ConduitBankBulkImportView.as_view(), name='conduitbank_import'),
    path('conduit-banks/edit/', views.ConduitBankBulkEditView.as_view(), name='conduitbank_bulk_edit'),
    path('conduit-banks/delete/', views.ConduitBankBulkDeleteView.as_view(), name='conduitbank_bulk_delete'),
    path('conduit-banks/<int:pk>/', views.ConduitBankView.as_view(), name='conduitbank'),
    path('conduit-banks/<int:pk>/edit/', views.ConduitBankEditView.as_view(), name='conduitbank_edit'),
    path('conduit-banks/<int:pk>/delete/', views.ConduitBankDeleteView.as_view(), name='conduitbank_delete'),

    # Conduit Junctions
    path('junctions/', views.ConduitJunctionListView.as_view(), name='conduitjunction_list'),
    path('junctions/add/', views.ConduitJunctionEditView.as_view(), name='conduitjunction_add'),
    path('junctions/<int:pk>/', views.ConduitJunctionView.as_view(), name='conduitjunction'),
    path('junctions/<int:pk>/edit/', views.ConduitJunctionEditView.as_view(), name='conduitjunction_edit'),
    path('junctions/<int:pk>/delete/', views.ConduitJunctionDeleteView.as_view(), name='conduitjunction_delete'),

    # Pathway Locations (waypoints)
    path('pathway-locations/', views.PathwayLocationListView.as_view(), name='pathwaylocation_list'),
    path('pathway-locations/add/', views.PathwayLocationEditView.as_view(), name='pathwaylocation_add'),
    path('pathway-locations/<int:pk>/', views.PathwayLocationView.as_view(), name='pathwaylocation'),
    path('pathway-locations/<int:pk>/edit/', views.PathwayLocationEditView.as_view(), name='pathwaylocation_edit'),
    path('pathway-locations/<int:pk>/delete/', views.PathwayLocationDeleteView.as_view(), name='pathwaylocation_delete'),

    # Cable Segments
    path('cable-segments/', views.CableSegmentListView.as_view(), name='cablesegment_list'),
    path('cable-segments/add/', views.CableSegmentEditView.as_view(), name='cablesegment_add'),
    path('cable-segments/import/', views.CableSegmentBulkImportView.as_view(), name='cablesegment_import'),
    path('cable-segments/delete/', views.CableSegmentBulkDeleteView.as_view(), name='cablesegment_bulk_delete'),
    path('cable-segments/<int:pk>/', views.CableSegmentView.as_view(), name='cablesegment'),
    path('cable-segments/<int:pk>/edit/', views.CableSegmentEditView.as_view(), name='cablesegment_edit'),
    path('cable-segments/<int:pk>/delete/', views.CableSegmentDeleteView.as_view(), name='cablesegment_delete'),

    # Pull Sheets
    path('pull-sheets/', views.PullSheetListView.as_view(), name='pullsheet_list'),
    path('pull-sheets/<int:cable_pk>/', views.PullSheetDetailView.as_view(), name='pullsheet_detail'),

    # Map
    path('map/', views.MapView.as_view(), name='map'),

    # Graph Traversal Tools
    path('route-finder/', views.RouteFinderView.as_view(), name='route_finder'),
    path('cable-trace/', views.CableTraceView.as_view(), name='cable_trace'),
    path('neighbors/', views.NeighborsView.as_view(), name='neighbors'),
]
