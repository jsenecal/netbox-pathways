from django.db.models import Q
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from . import filters, forms, models, tables

# --- Structure ---

class StructureListView(generic.ObjectListView):
    queryset = models.Structure.objects.all()
    table = tables.StructureTable
    filterset = filters.StructureFilterSet


class StructureView(generic.ObjectView):
    queryset = models.Structure.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'pathways_in': instance.pathways_in.select_related('start_structure'),
            'pathways_out': instance.pathways_out.select_related('end_structure'),
            'conduit_banks': instance.conduit_banks.all(),
        }


class StructureEditView(generic.ObjectEditView):
    queryset = models.Structure.objects.all()
    form = forms.StructureForm


class StructureDeleteView(generic.ObjectDeleteView):
    queryset = models.Structure.objects.all()


class StructureBulkImportView(generic.BulkImportView):
    queryset = models.Structure.objects.all()
    model_form = forms.StructureImportForm


class StructureBulkEditView(generic.BulkEditView):
    queryset = models.Structure.objects.all()
    filterset = filters.StructureFilterSet
    table = tables.StructureTable
    form = forms.StructureBulkEditForm


class StructureBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Structure.objects.all()
    table = tables.StructureTable


@register_model_view(models.Structure, 'pathways')
class StructurePathwaysView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.Pathway
    table = tables.PathwayTable
    filterset = filters.PathwayFilterSet
    tab = ViewTab(
        label='Pathways',
        badge=lambda obj: obj.pathways_out.count() + obj.pathways_in.count(),
    )

    def get_children(self, request, parent):
        return models.Pathway.objects.filter(
            Q(start_structure=parent) | Q(end_structure=parent)
        )


@register_model_view(models.Structure, 'conduit_banks')
class StructureConduitBanksView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.ConduitBank
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet
    tab = ViewTab(
        label='Conduit Banks',
        badge=lambda obj: obj.conduit_banks.count(),
    )

    def get_children(self, request, parent):
        return parent.conduit_banks.all()


# --- Pathway (base) ---

class PathwayListView(generic.ObjectListView):
    queryset = models.Pathway.objects.all()
    table = tables.PathwayTable
    filterset = filters.PathwayFilterSet


class PathwayView(generic.ObjectView):
    queryset = models.Pathway.objects.all()

    def get_extra_context(self, request, instance):
        cable_segments = instance.cable_segments.select_related('cable')
        specific = instance
        if instance.pathway_type == 'conduit':
            specific = instance.conduit
        elif instance.pathway_type == 'aerial':
            specific = instance.aerialspan
        elif instance.pathway_type == 'direct_buried':
            specific = instance.directburied
        elif instance.pathway_type == 'innerduct':
            specific = instance.innerduct
        return {
            'cable_segments': cable_segments,
            'utilization': instance.utilization_percentage,
            'specific_instance': specific,
        }


# --- Conduit ---

class ConduitListView(generic.ObjectListView):
    queryset = models.Conduit.objects.all()
    table = tables.ConduitTable
    filterset = filters.ConduitFilterSet


class ConduitView(generic.ObjectView):
    queryset = models.Conduit.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'cable_segments': instance.cable_segments.select_related('cable'),
            'innerducts': instance.innerducts.all(),
            'utilization': instance.utilization_percentage,
        }


class ConduitEditView(generic.ObjectEditView):
    queryset = models.Conduit.objects.all()
    form = forms.ConduitForm


class ConduitDeleteView(generic.ObjectDeleteView):
    queryset = models.Conduit.objects.all()


class ConduitBulkImportView(generic.BulkImportView):
    queryset = models.Conduit.objects.all()
    model_form = forms.ConduitImportForm


class ConduitBulkEditView(generic.BulkEditView):
    queryset = models.Conduit.objects.all()
    filterset = filters.ConduitFilterSet
    table = tables.ConduitTable
    form = forms.ConduitBulkEditForm


class ConduitBulkDeleteView(generic.BulkDeleteView):
    queryset = models.Conduit.objects.all()
    table = tables.ConduitTable


@register_model_view(models.Conduit, 'innerducts')
class ConduitInnerductsView(generic.ObjectChildrenView):
    queryset = models.Conduit.objects.all()
    child_model = models.Innerduct
    table = tables.InnerductTable
    filterset = filters.InnerductFilterSet
    tab = ViewTab(
        label='Innerducts',
        badge=lambda obj: obj.innerducts.count(),
    )

    def get_children(self, request, parent):
        return parent.innerducts.all()


# --- Aerial Span ---

class AerialSpanListView(generic.ObjectListView):
    queryset = models.AerialSpan.objects.all()
    table = tables.AerialSpanTable
    filterset = filters.AerialSpanFilterSet


class AerialSpanView(generic.ObjectView):
    queryset = models.AerialSpan.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'cable_segments': instance.cable_segments.select_related('cable'),
            'utilization': instance.utilization_percentage,
        }


class AerialSpanEditView(generic.ObjectEditView):
    queryset = models.AerialSpan.objects.all()
    form = forms.AerialSpanForm


class AerialSpanDeleteView(generic.ObjectDeleteView):
    queryset = models.AerialSpan.objects.all()


class AerialSpanBulkImportView(generic.BulkImportView):
    queryset = models.AerialSpan.objects.all()
    model_form = forms.AerialSpanImportForm


class AerialSpanBulkEditView(generic.BulkEditView):
    queryset = models.AerialSpan.objects.all()
    filterset = filters.AerialSpanFilterSet
    table = tables.AerialSpanTable
    form = forms.AerialSpanBulkEditForm


class AerialSpanBulkDeleteView(generic.BulkDeleteView):
    queryset = models.AerialSpan.objects.all()
    table = tables.AerialSpanTable


# --- Direct Buried ---

class DirectBuriedListView(generic.ObjectListView):
    queryset = models.DirectBuried.objects.all()
    table = tables.DirectBuriedTable
    filterset = filters.DirectBuriedFilterSet


class DirectBuriedView(generic.ObjectView):
    queryset = models.DirectBuried.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'cable_segments': instance.cable_segments.select_related('cable'),
            'utilization': instance.utilization_percentage,
        }


class DirectBuriedEditView(generic.ObjectEditView):
    queryset = models.DirectBuried.objects.all()
    form = forms.DirectBuriedForm


class DirectBuriedDeleteView(generic.ObjectDeleteView):
    queryset = models.DirectBuried.objects.all()


# --- Innerduct ---

class InnerductListView(generic.ObjectListView):
    queryset = models.Innerduct.objects.all()
    table = tables.InnerductTable
    filterset = filters.InnerductFilterSet


class InnerductView(generic.ObjectView):
    queryset = models.Innerduct.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'cable_segments': instance.cable_segments.select_related('cable'),
            'utilization': instance.utilization_percentage,
            'parent_conduit': instance.parent_conduit,
        }


class InnerductEditView(generic.ObjectEditView):
    queryset = models.Innerduct.objects.all()
    form = forms.InnerductForm


class InnerductDeleteView(generic.ObjectDeleteView):
    queryset = models.Innerduct.objects.all()


# --- Conduit Bank ---

class ConduitBankListView(generic.ObjectListView):
    queryset = models.ConduitBank.objects.all()
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet


class ConduitBankView(generic.ObjectView):
    queryset = models.ConduitBank.objects.all()

    def get_extra_context(self, request, instance):
        conduits = instance.conduits.all()
        return {
            'conduits': conduits,
            'conduit_count': conduits.count(),
            'utilization': f"{conduits.count()}/{instance.total_conduits}",
        }


class ConduitBankEditView(generic.ObjectEditView):
    queryset = models.ConduitBank.objects.all()
    form = forms.ConduitBankForm


class ConduitBankDeleteView(generic.ObjectDeleteView):
    queryset = models.ConduitBank.objects.all()


class ConduitBankBulkImportView(generic.BulkImportView):
    queryset = models.ConduitBank.objects.all()
    model_form = forms.ConduitBankImportForm


class ConduitBankBulkEditView(generic.BulkEditView):
    queryset = models.ConduitBank.objects.all()
    filterset = filters.ConduitBankFilterSet
    table = tables.ConduitBankTable
    form = forms.ConduitBankBulkEditForm


class ConduitBankBulkDeleteView(generic.BulkDeleteView):
    queryset = models.ConduitBank.objects.all()
    table = tables.ConduitBankTable


# --- Conduit Junction ---

class ConduitJunctionListView(generic.ObjectListView):
    queryset = models.ConduitJunction.objects.all()
    table = tables.ConduitJunctionTable
    filterset = filters.ConduitJunctionFilterSet


class ConduitJunctionView(generic.ObjectView):
    queryset = models.ConduitJunction.objects.all()

    def get_extra_context(self, request, instance):
        return {
            'trunk_conduit': instance.trunk_conduit,
            'branch_conduit': instance.branch_conduit,
            'location': instance.location,
            'position_percent': f"{instance.position_on_trunk * 100:.1f}%",
        }


class ConduitJunctionEditView(generic.ObjectEditView):
    queryset = models.ConduitJunction.objects.all()
    form = forms.ConduitJunctionForm


class ConduitJunctionDeleteView(generic.ObjectDeleteView):
    queryset = models.ConduitJunction.objects.all()


# --- Cable Segment ---

class CableSegmentListView(generic.ObjectListView):
    queryset = models.CableSegment.objects.all()
    table = tables.CableSegmentTable
    filterset = filters.CableSegmentFilterSet


class CableSegmentView(generic.ObjectView):
    queryset = models.CableSegment.objects.all()


class CableSegmentEditView(generic.ObjectEditView):
    queryset = models.CableSegment.objects.all()
    form = forms.CableSegmentForm


class CableSegmentDeleteView(generic.ObjectDeleteView):
    queryset = models.CableSegment.objects.all()


class CableSegmentBulkImportView(generic.BulkImportView):
    queryset = models.CableSegment.objects.all()
    model_form = forms.CableSegmentImportForm


class CableSegmentBulkDeleteView(generic.BulkDeleteView):
    queryset = models.CableSegment.objects.all()
    table = tables.CableSegmentTable


# --- Map View ---

class MapView(generic.ObjectListView):
    queryset = models.Structure.objects.all()
    template_name = 'netbox_pathways/map.html'

    def get_extra_context(self, request):
        structures = models.Structure.objects.select_related('site')
        pathways = models.Pathway.objects.select_related('start_structure', 'end_structure')

        structures_geojson = []
        for structure in structures:
            if structure.location:
                structures_geojson.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [structure.location.x, structure.location.y],
                    },
                    'properties': {
                        'id': structure.pk,
                        'name': structure.name,
                        'type': structure.get_structure_type_display() if structure.structure_type else 'Unknown',
                        'site': structure.site.name,
                        'url': structure.get_absolute_url(),
                    },
                })

        pathways_geojson = []
        for pathway in pathways:
            if pathway.path:
                coords = [[point[0], point[1]] for point in pathway.path.coords]
                pathways_geojson.append({
                    'type': 'Feature',
                    'geometry': {
                        'type': 'LineString',
                        'coordinates': coords,
                    },
                    'properties': {
                        'id': pathway.pk,
                        'name': pathway.name,
                        'pathway_type': pathway.get_pathway_type_display(),
                        'utilization': pathway.utilization_percentage,
                        'url': pathway.get_absolute_url(),
                    },
                })

        return {
            'structures_geojson': structures_geojson,
            'pathways_geojson': pathways_geojson,
            'map_center_lat': request.GET.get('lat', 45.5017),
            'map_center_lon': request.GET.get('lon', -73.5673),
            'map_zoom': request.GET.get('zoom', 10),
        }
