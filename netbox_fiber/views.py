from django.contrib.gis.geos import Point, LineString
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from . import models, tables, forms, filters
from django.http import HttpResponse
from .models import (
    FiberStructure, FiberPathway, FiberConduit, FiberAerialSpan, 
    FiberDirectBuried, FiberInnerduct, FiberSplice, FiberCableSegment,
    ConduitBank, ConduitJunction, FiberCable, SpliceConnection
)
from .svg import generate_splice_diagram


class FiberStructureListView(generic.ObjectListView):
    queryset = FiberStructure.objects.all()
    table = tables.FiberStructureTable
    filterset = filters.FiberStructureFilterSet


class FiberStructureView(generic.ObjectView):
    queryset = FiberStructure.objects.all()

    def get_extra_context(self, request, instance):
        pathways_in = instance.pathways_in.select_related('start_structure')
        pathways_out = instance.pathways_out.select_related('end_structure')
        
        return {
            'pathways_in': pathways_in,
            'pathways_out': pathways_out,
            'splice_count': instance.splices.count(),
        }


class FiberStructureEditView(generic.ObjectEditView):
    queryset = FiberStructure.objects.all()
    form = forms.FiberStructureForm


class FiberStructureDeleteView(generic.ObjectDeleteView):
    queryset = FiberStructure.objects.all()


class FiberStructureBulkImportView(generic.BulkImportView):
    queryset = FiberStructure.objects.all()
    model_form = forms.FiberStructureImportForm


class FiberStructureBulkEditView(generic.BulkEditView):
    queryset = FiberStructure.objects.all()
    filterset = filters.FiberStructureFilterSet
    table = tables.FiberStructureTable
    form = forms.FiberStructureBulkEditForm


class FiberStructureBulkDeleteView(generic.BulkDeleteView):
    queryset = FiberStructure.objects.all()
    table = tables.FiberStructureTable


# Base Pathway Views
class FiberPathwayListView(generic.ObjectListView):
    queryset = FiberPathway.objects.all()
    table = tables.FiberPathwayTable
    filterset = filters.FiberPathwayFilterSet
    template_name = 'netbox_fiber/pathway_list.html'


class FiberPathwayView(generic.ObjectView):
    queryset = FiberPathway.objects.all()

    def get_extra_context(self, request, instance):
        cable_segments = instance.cable_segments.select_related('cable')
        
        # Get the specific subclass instance
        if instance.pathway_type == 'conduit':
            instance = instance.fiberconduit
        elif instance.pathway_type == 'aerial':
            instance = instance.fiberaerialspan
        elif instance.pathway_type == 'direct_buried':
            instance = instance.fiberdirectburied
        elif instance.pathway_type == 'innerduct':
            instance = instance.fiberinnerduct
        
        return {
            'cable_segments': cable_segments,
            'utilization': instance.utilization_percentage,
            'specific_instance': instance,
        }


# Conduit Views
class FiberConduitListView(generic.ObjectListView):
    queryset = FiberConduit.objects.all()
    table = tables.FiberConduitTable
    filterset = filters.FiberConduitFilterSet


class FiberConduitView(generic.ObjectView):
    queryset = FiberConduit.objects.all()

    def get_extra_context(self, request, instance):
        cable_segments = instance.cable_segments.select_related('cable')
        innerducts = instance.innerducts.all()
        
        return {
            'cable_segments': cable_segments,
            'innerducts': innerducts,
            'utilization': instance.utilization_percentage,
        }


class FiberConduitEditView(generic.ObjectEditView):
    queryset = FiberConduit.objects.all()
    form = forms.FiberConduitForm


class FiberConduitDeleteView(generic.ObjectDeleteView):
    queryset = FiberConduit.objects.all()


class FiberConduitBulkImportView(generic.BulkImportView):
    queryset = FiberConduit.objects.all()
    model_form = forms.FiberConduitImportForm


class FiberConduitBulkEditView(generic.BulkEditView):
    queryset = FiberConduit.objects.all()
    filterset = filters.FiberConduitFilterSet
    table = tables.FiberConduitTable
    form = forms.FiberConduitBulkEditForm


class FiberConduitBulkDeleteView(generic.BulkDeleteView):
    queryset = FiberConduit.objects.all()
    table = tables.FiberConduitTable


# Aerial Span Views
class FiberAerialSpanListView(generic.ObjectListView):
    queryset = FiberAerialSpan.objects.all()
    table = tables.FiberAerialSpanTable
    filterset = filters.FiberAerialSpanFilterSet


class FiberAerialSpanView(generic.ObjectView):
    queryset = FiberAerialSpan.objects.all()

    def get_extra_context(self, request, instance):
        cable_segments = instance.cable_segments.select_related('cable')
        
        return {
            'cable_segments': cable_segments,
            'utilization': instance.utilization_percentage,
        }


class FiberAerialSpanEditView(generic.ObjectEditView):
    queryset = FiberAerialSpan.objects.all()
    form = forms.FiberAerialSpanForm


class FiberAerialSpanDeleteView(generic.ObjectDeleteView):
    queryset = FiberAerialSpan.objects.all()


class FiberAerialSpanBulkImportView(generic.BulkImportView):
    queryset = FiberAerialSpan.objects.all()
    model_form = forms.FiberAerialSpanImportForm


class FiberAerialSpanBulkEditView(generic.BulkEditView):
    queryset = FiberAerialSpan.objects.all()
    filterset = filters.FiberAerialSpanFilterSet
    table = tables.FiberAerialSpanTable
    form = forms.FiberAerialSpanBulkEditForm


class FiberAerialSpanBulkDeleteView(generic.BulkDeleteView):
    queryset = FiberAerialSpan.objects.all()
    table = tables.FiberAerialSpanTable


# Direct Buried Views
class FiberDirectBuriedListView(generic.ObjectListView):
    queryset = FiberDirectBuried.objects.all()
    table = tables.FiberDirectBuriedTable
    filterset = filters.FiberDirectBuriedFilterSet


class FiberDirectBuriedView(generic.ObjectView):
    queryset = FiberDirectBuried.objects.all()

    def get_extra_context(self, request, instance):
        cable_segments = instance.cable_segments.select_related('cable')
        
        return {
            'cable_segments': cable_segments,
            'utilization': instance.utilization_percentage,
        }


class FiberDirectBuriedEditView(generic.ObjectEditView):
    queryset = FiberDirectBuried.objects.all()
    form = forms.FiberDirectBuriedForm


class FiberDirectBuriedDeleteView(generic.ObjectDeleteView):
    queryset = FiberDirectBuried.objects.all()


# Innerduct Views
class FiberInnerductListView(generic.ObjectListView):
    queryset = FiberInnerduct.objects.all()
    table = tables.FiberInnerductTable
    filterset = filters.FiberInnerductFilterSet


class FiberInnerductView(generic.ObjectView):
    queryset = FiberInnerduct.objects.all()

    def get_extra_context(self, request, instance):
        cable_segments = instance.cable_segments.select_related('cable')
        
        return {
            'cable_segments': cable_segments,
            'utilization': instance.utilization_percentage,
            'parent_conduit': instance.parent_conduit,
        }


class FiberInnerductEditView(generic.ObjectEditView):
    queryset = FiberInnerduct.objects.all()
    form = forms.FiberInnerductForm


class FiberInnerductDeleteView(generic.ObjectDeleteView):
    queryset = FiberInnerduct.objects.all()


# Conduit Bank Views
class ConduitBankListView(generic.ObjectListView):
    queryset = ConduitBank.objects.all()
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet


class ConduitBankView(generic.ObjectView):
    queryset = ConduitBank.objects.all()

    def get_extra_context(self, request, instance):
        conduits = instance.conduits.all()
        
        return {
            'conduits': conduits,
            'conduit_count': conduits.count(),
            'utilization': f"{conduits.count()}/{instance.total_conduits}",
        }


class ConduitBankEditView(generic.ObjectEditView):
    queryset = ConduitBank.objects.all()
    form = forms.ConduitBankForm


class ConduitBankDeleteView(generic.ObjectDeleteView):
    queryset = ConduitBank.objects.all()


class ConduitBankBulkImportView(generic.BulkImportView):
    queryset = ConduitBank.objects.all()
    model_form = forms.ConduitBankImportForm


class ConduitBankBulkEditView(generic.BulkEditView):
    queryset = ConduitBank.objects.all()
    filterset = filters.ConduitBankFilterSet
    table = tables.ConduitBankTable
    form = forms.ConduitBankBulkEditForm


class ConduitBankBulkDeleteView(generic.BulkDeleteView):
    queryset = ConduitBank.objects.all()
    table = tables.ConduitBankTable


# Conduit Junction Views
class ConduitJunctionListView(generic.ObjectListView):
    queryset = ConduitJunction.objects.all()
    table = tables.ConduitJunctionTable
    filterset = filters.ConduitJunctionFilterSet


class ConduitJunctionView(generic.ObjectView):
    queryset = ConduitJunction.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'trunk_conduit': instance.trunk_conduit,
            'branch_conduit': instance.branch_conduit,
            'location': instance.location,
            'position_percent': f"{instance.position_on_trunk * 100:.1f}%",
        }


class ConduitJunctionEditView(generic.ObjectEditView):
    queryset = ConduitJunction.objects.all()
    form = forms.ConduitJunctionForm


class ConduitJunctionDeleteView(generic.ObjectDeleteView):
    queryset = ConduitJunction.objects.all()


# Map View
class FiberMapView(generic.ObjectListView):
    """
    Interactive map view showing all fiber infrastructure
    """
    queryset = FiberStructure.objects.all()
    template_name = 'netbox_fiber/map.html'
    
    def get_extra_context(self, request):
        structures = FiberStructure.objects.select_related('site')
        pathways = FiberPathway.objects.select_related('start_structure', 'end_structure')
        
        # Convert to GeoJSON for Leaflet
        structures_geojson = []
        for structure in structures:
            if structure.location:
                structures_geojson.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [structure.location.x, structure.location.y]
                    },
                    'properties': {
                        'id': structure.pk,
                        'name': structure.name,
                        'type': structure.get_structure_type_display(),
                        'site': structure.site.name,
                        'url': structure.get_absolute_url(),
                    }
                })
        
        pathways_geojson = []
        for pathway in pathways:
            if pathway.path:
                coords = [[point[0], point[1]] for point in pathway.path.coords]
                
                # Get specific attributes based on pathway type
                pathway_info = {
                    'id': pathway.pk,
                    'name': pathway.name,
                    'pathway_type': pathway.get_pathway_type_display(),
                    'utilization': pathway.utilization_percentage,
                    'url': pathway.get_absolute_url(),
                }
                
                # Add type-specific attributes
                if pathway.pathway_type == 'conduit':
                    try:
                        conduit = pathway.fiberconduit
                        pathway_info['material'] = conduit.get_material_display() if conduit.material else None
                        pathway_info['duct_count'] = conduit.duct_count
                    except:
                        pass
                elif pathway.pathway_type == 'aerial':
                    try:
                        aerial = pathway.fiberaerialspan
                        pathway_info['aerial_type'] = aerial.get_aerial_type_display()
                    except:
                        pass
                
                pathways_geojson.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': coords
                    },
                    'properties': pathway_info
                })
        
        return {
            'structures_geojson': structures_geojson,
            'pathways_geojson': pathways_geojson,
            'map_center_lat': self.request.GET.get('lat', 39.8283),
            'map_center_lon': self.request.GET.get('lon', -98.5795),
            'map_zoom': self.request.GET.get('zoom', 5),
        }


@register_model_view(FiberStructure, 'pathways')
class FiberStructurePathwaysView(generic.ObjectChildrenView):
    queryset = FiberStructure.objects.all()
    child_model = FiberPathway
    table = tables.FiberPathwayTable
    filterset = filters.FiberPathwayFilterSet
    tab = ViewTab(
        label='Pathways',
        badge=lambda obj: obj.pathways_out.count() + obj.pathways_in.count(),
    )

    def get_children(self, request, parent):
        return FiberPathway.objects.filter(
            Q(start_structure=parent) | Q(end_structure=parent)
        )


@register_model_view(FiberConduit, 'innerducts')
class FiberConduitInnerductsView(generic.ObjectChildrenView):
    queryset = FiberConduit.objects.all()
    child_model = FiberInnerduct
    table = tables.FiberInnerductTable
    filterset = filters.FiberInnerductFilterSet
    tab = ViewTab(
        label='Innerducts',
        badge=lambda obj: obj.innerducts.count(),
    )

    def get_children(self, request, parent):
        return parent.innerducts.all()


# Fiber Cable Views
class FiberCableListView(generic.ObjectListView):
    queryset = FiberCable.objects.all()
    table = tables.FiberCableTable
    filterset = filters.FiberCableFilterSet


class FiberCableView(generic.ObjectView):
    queryset = FiberCable.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'cable': instance.cable,
            'segments': instance.cable.fiber_segments.all() if hasattr(instance.cable, 'fiber_segments') else [],
        }


class FiberCableEditView(generic.ObjectEditView):
    queryset = FiberCable.objects.all()
    form = forms.FiberCableForm


class FiberCableDeleteView(generic.ObjectDeleteView):
    queryset = FiberCable.objects.all()


# Splice Connection Views
class SpliceConnectionListView(generic.ObjectListView):
    queryset = SpliceConnection.objects.all()
    table = tables.SpliceConnectionTable
    filterset = filters.SpliceConnectionFilterSet


class SpliceConnectionView(generic.ObjectView):
    queryset = SpliceConnection.objects.all()


class SpliceConnectionEditView(generic.ObjectEditView):
    queryset = SpliceConnection.objects.all()
    form = forms.SpliceConnectionForm


class SpliceConnectionDeleteView(generic.ObjectDeleteView):
    queryset = SpliceConnection.objects.all()


# Splice Diagram View
def splice_diagram_view(request, device_id):
    """Generate and display SVG splice diagram for a device"""
    from dcim.models import Device
    
    device = get_object_or_404(Device, pk=device_id)
    
    # Check if this should return SVG or HTML
    if request.GET.get('format') == 'svg':
        # Return raw SVG
        svg_content = generate_splice_diagram(device_id)
        if svg_content:
            return HttpResponse(svg_content, content_type='image/svg+xml')
        else:
            return HttpResponse("Error generating diagram", status=500)
    
    # Return HTML page with embedded SVG
    context = {
        'device': device,
        'svg_url': f"?format=svg",
        'splice_count': SpliceConnection.objects.filter(device=device).count(),
    }
    return render(request, 'netbox_fiber/splice_diagram.html', context)


@register_model_view(Device, 'fiber_splices')
class DeviceFiberSplicesView(generic.ObjectChildrenView):
    """View for splice connections within a device"""
    queryset = Device.objects.all()
    child_model = SpliceConnection
    table = tables.SpliceConnectionTable
    filterset = filters.SpliceConnectionFilterSet
    template_name = 'netbox_fiber/device_splices.html'
    tab = ViewTab(
        label='Fiber Splices',
        badge=lambda obj: obj.splice_connections.count() if hasattr(obj, 'splice_connections') else 0,
        permission='netbox_fiber.view_spliceconnection',
        hide_if_empty=True
    )

    def get_children(self, request, parent):
        return SpliceConnection.objects.filter(device=parent)
    
    def get_extra_context(self, request, instance):
        return {
            'splice_diagram_url': reverse('plugins:netbox_fiber:device_splice_diagram', args=[instance.pk]),
        }