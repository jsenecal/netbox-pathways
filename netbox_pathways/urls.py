from django.urls import include, path
from utilities.urls import get_model_urls

from . import views

urlpatterns = [
    # Structures
    path("structures/", views.StructureListView.as_view(), name="structure_list"),
    path("structures/add/", views.StructureEditView.as_view(), name="structure_add"),
    path("structures/import/", views.StructureBulkImportView.as_view(), name="structure_bulk_import"),
    path("structures/edit/", views.StructureBulkEditView.as_view(), name="structure_bulk_edit"),
    path("structures/delete/", views.StructureBulkDeleteView.as_view(), name="structure_bulk_delete"),
    path(
        "structures/<int:pk>/",
        include(
            [
                path("", views.StructureView.as_view(), name="structure"),
                path("edit/", views.StructureEditView.as_view(), name="structure_edit"),
                path("create-site/", views.StructureCreateSiteView.as_view(), name="structure_create_site"),
                path("delete/", views.StructureDeleteView.as_view(), name="structure_delete"),
                *get_model_urls("netbox_pathways", "structure"),
            ]
        ),
    ),
    # Pathways (every type)
    path("pathways/", views.PathwayListView.as_view(), name="pathway_list"),
    path("pathways/add/", views.PathwayEditView.as_view(), name="pathway_add"),
    path("pathways/import/", views.PathwayBulkImportView.as_view(), name="pathway_bulk_import"),
    path("pathways/edit/", views.PathwayBulkEditView.as_view(), name="pathway_bulk_edit"),
    path("pathways/delete/", views.PathwayBulkDeleteView.as_view(), name="pathway_bulk_delete"),
    path(
        "pathways/<int:pk>/",
        include(
            [
                path("", views.PathwayView.as_view(), name="pathway"),
                path("edit/", views.PathwayEditView.as_view(), name="pathway_edit"),
                path("delete/", views.PathwayDeleteView.as_view(), name="pathway_delete"),
                *get_model_urls("netbox_pathways", "pathway"),
            ]
        ),
    ),
    # Conduit Junctions
    path("junctions/", views.ConduitJunctionListView.as_view(), name="conduitjunction_list"),
    path("junctions/add/", views.ConduitJunctionEditView.as_view(), name="conduitjunction_add"),
    path("junctions/import/", views.ConduitJunctionBulkImportView.as_view(), name="conduitjunction_bulk_import"),
    path(
        "junctions/<int:pk>/",
        include(
            [
                path("", views.ConduitJunctionView.as_view(), name="conduitjunction"),
                path("edit/", views.ConduitJunctionEditView.as_view(), name="conduitjunction_edit"),
                path("delete/", views.ConduitJunctionDeleteView.as_view(), name="conduitjunction_delete"),
                *get_model_urls("netbox_pathways", "conduitjunction"),
            ]
        ),
    ),
    # Pathway Locations (waypoints)
    path("pathway-locations/", views.PathwayLocationListView.as_view(), name="pathwaylocation_list"),
    path("pathway-locations/add/", views.PathwayLocationEditView.as_view(), name="pathwaylocation_add"),
    path(
        "pathway-locations/<int:pk>/",
        include(
            [
                path("", views.PathwayLocationView.as_view(), name="pathwaylocation"),
                path("edit/", views.PathwayLocationEditView.as_view(), name="pathwaylocation_edit"),
                path("delete/", views.PathwayLocationDeleteView.as_view(), name="pathwaylocation_delete"),
                *get_model_urls("netbox_pathways", "pathwaylocation"),
            ]
        ),
    ),
    # Cable Segments
    path("cable-segments/", views.CableSegmentListView.as_view(), name="cablesegment_list"),
    path("cable-segments/add/", views.CableSegmentEditView.as_view(), name="cablesegment_add"),
    path("cable-segments/import/", views.CableSegmentBulkImportView.as_view(), name="cablesegment_bulk_import"),
    path("cable-segments/edit/", views.CableSegmentBulkEditView.as_view(), name="cablesegment_bulk_edit"),
    path("cable-segments/delete/", views.CableSegmentBulkDeleteView.as_view(), name="cablesegment_bulk_delete"),
    path(
        "cable-segments/<int:pk>/",
        include(
            [
                path("", views.CableSegmentView.as_view(), name="cablesegment"),
                path("edit/", views.CableSegmentEditView.as_view(), name="cablesegment_edit"),
                path("delete/", views.CableSegmentDeleteView.as_view(), name="cablesegment_delete"),
                *get_model_urls("netbox_pathways", "cablesegment"),
            ]
        ),
    ),
    # Site Geometries
    path("site-geometries/", views.SiteGeometryListView.as_view(), name="sitegeometry_list"),
    path("site-geometries/add/", views.SiteGeometryEditView.as_view(), name="sitegeometry_add"),
    path("site-geometries/import/", views.SiteGeometryBulkImportView.as_view(), name="sitegeometry_bulk_import"),
    path(
        "site-geometries/<int:pk>/",
        include(
            [
                path("", views.SiteGeometryView.as_view(), name="sitegeometry"),
                path("edit/", views.SiteGeometryEditView.as_view(), name="sitegeometry_edit"),
                path("delete/", views.SiteGeometryDeleteView.as_view(), name="sitegeometry_delete"),
                *get_model_urls("netbox_pathways", "sitegeometry"),
            ]
        ),
    ),
    # Circuit Geometries
    path("circuit-geometries/", views.CircuitGeometryListView.as_view(), name="circuitgeometry_list"),
    path("circuit-geometries/add/", views.CircuitGeometryEditView.as_view(), name="circuitgeometry_add"),
    path(
        "circuit-geometries/import/",
        views.CircuitGeometryBulkImportView.as_view(),
        name="circuitgeometry_bulk_import",
    ),
    path(
        "circuit-geometries/<int:pk>/",
        include(
            [
                path("", views.CircuitGeometryView.as_view(), name="circuitgeometry"),
                path("edit/", views.CircuitGeometryEditView.as_view(), name="circuitgeometry_edit"),
                path("delete/", views.CircuitGeometryDeleteView.as_view(), name="circuitgeometry_delete"),
                *get_model_urls("netbox_pathways", "circuitgeometry"),
            ]
        ),
    ),
    # Planned Routes
    path("planned-routes/", views.PlannedRouteListView.as_view(), name="plannedroute_list"),
    path("planned-routes/add/", views.PlannedRouteEditView.as_view(), name="plannedroute_add"),
    path("planned-routes/import/", views.PlannedRouteBulkImportView.as_view(), name="plannedroute_bulk_import"),
    path("planned-routes/edit/", views.PlannedRouteBulkEditView.as_view(), name="plannedroute_bulk_edit"),
    path("planned-routes/delete/", views.PlannedRouteBulkDeleteView.as_view(), name="plannedroute_bulk_delete"),
    path(
        "planned-routes/<int:pk>/",
        include(
            [
                path("", views.PlannedRouteView.as_view(), name="plannedroute"),
                path("edit/", views.PlannedRouteEditView.as_view(), name="plannedroute_edit"),
                path("delete/", views.PlannedRouteDeleteView.as_view(), name="plannedroute_delete"),
                path("split/", views.PlannedRouteSplitView.as_view(), name="plannedroute_split"),
                path("revert/", views.PlannedRouteRevertSplitView.as_view(), name="plannedroute_revert"),
                path("apply/", views.PlannedRouteApplyView.as_view(), name="plannedroute_apply"),
                *get_model_urls("netbox_pathways", "plannedroute"),
            ]
        ),
    ),
    # Route Planner
    path("route-planner/", views.RoutePlannerView.as_view(), name="route_planner"),
    path("route-planner/find/", views.RoutePlannerFindView.as_view(), name="route_planner_find"),
    path("route-planner/save/", views.RoutePlannerSaveView.as_view(), name="route_planner_save"),
    path("route-planner/constraint/", views.RoutePlannerConstraintView.as_view(), name="route_planner_constraint"),
    # Pull Sheets
    path("pull-sheets/", views.PullSheetListView.as_view(), name="pullsheet_list"),
    path("pull-sheets/<int:cable_pk>/", views.PullSheetDetailView.as_view(), name="pullsheet_detail"),
    # Map
    path("map/", views.MapView.as_view(), name="map"),
    # Cable routing panel HTMX endpoints
    path(
        "cable-routing/<int:cable_pk>/add-segment/",
        views.CableRoutingAddSegmentView.as_view(),
        name="cable_routing_add",
    ),
    path(
        "cable-routing/<int:cable_pk>/delete-segment/<int:segment_pk>/",
        views.CableRoutingDeleteSegmentView.as_view(),
        name="cable_routing_delete",
    ),
    path(
        "cable-routing/<int:cable_pk>/find-route/", views.CableRoutingFindRouteView.as_view(), name="cable_routing_find"
    ),
    path(
        "cable-routing/<int:cable_pk>/apply-route/",
        views.CableRoutingApplyRouteView.as_view(),
        name="cable_routing_apply",
    ),
    path("cable-routing/<int:cable_pk>/table/", views.CableRoutingTableView.as_view(), name="cable_routing_table"),
]
