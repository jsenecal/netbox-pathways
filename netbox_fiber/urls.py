from django.urls import path
from . import views

urlpatterns = [
    # Fiber Structures
    path('structures/', views.FiberStructureListView.as_view(), name='fiberstructure_list'),
    path('structures/add/', views.FiberStructureEditView.as_view(), name='fiberstructure_add'),
    path('structures/import/', views.FiberStructureBulkImportView.as_view(), name='fiberstructure_import'),
    path('structures/edit/', views.FiberStructureBulkEditView.as_view(), name='fiberstructure_bulk_edit'),
    path('structures/delete/', views.FiberStructureBulkDeleteView.as_view(), name='fiberstructure_bulk_delete'),
    path('structures/<int:pk>/', views.FiberStructureView.as_view(), name='fiberstructure'),
    path('structures/<int:pk>/edit/', views.FiberStructureEditView.as_view(), name='fiberstructure_edit'),
    path('structures/<int:pk>/delete/', views.FiberStructureDeleteView.as_view(), name='fiberstructure_delete'),
    path('structures/<int:pk>/conduits/', views.FiberStructureConduitsView.as_view(), name='fiberstructure_conduits'),
    
    # Fiber Conduits
    path('conduits/', views.FiberConduitListView.as_view(), name='fiberconduit_list'),
    path('conduits/add/', views.FiberConduitEditView.as_view(), name='fiberconduit_add'),
    path('conduits/import/', views.FiberConduitBulkImportView.as_view(), name='fiberconduit_import'),
    path('conduits/edit/', views.FiberConduitBulkEditView.as_view(), name='fiberconduit_bulk_edit'),
    path('conduits/delete/', views.FiberConduitBulkDeleteView.as_view(), name='fiberconduit_bulk_delete'),
    path('conduits/<int:pk>/', views.FiberConduitView.as_view(), name='fiberconduit'),
    path('conduits/<int:pk>/edit/', views.FiberConduitEditView.as_view(), name='fiberconduit_edit'),
    path('conduits/<int:pk>/delete/', views.FiberConduitDeleteView.as_view(), name='fiberconduit_delete'),
    
    # Map View
    path('map/', views.FiberMapView.as_view(), name='fiber_map'),
]