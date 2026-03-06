from dcim.models import Cable
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, render
from django.views import View
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.ui import layout
from netbox.ui.panels import CommentsPanel, ObjectsTablePanel
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from . import filters, forms, models, tables
from .ui import panels

# --- Structure ---

class StructureListView(generic.ObjectListView):
    queryset = models.Structure.objects.select_related('site')
    table = tables.StructureTable
    filterset = filters.StructureFilterSet


class StructureView(generic.ObjectView):
    queryset = models.Structure.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.StructurePanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        right_panels=[],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.ConduitBank',
                title='Conduit Banks',
                filters={'structure_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


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
    queryset = models.Pathway.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location',
    )
    table = tables.PathwayTable
    filterset = filters.PathwayFilterSet


class PathwayView(generic.ObjectView):
    queryset = models.Pathway.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.PathwayPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.PathwayLocation',
                title='Waypoints',
                filters={'pathway_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


# --- Conduit ---

class ConduitListView(generic.ObjectListView):
    queryset = models.Conduit.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'conduit_bank',
    )
    table = tables.ConduitTable
    filterset = filters.ConduitFilterSet


class ConduitView(generic.ObjectView):
    queryset = models.Conduit.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.ConduitPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.Innerduct',
                title='Innerducts',
                filters={'parent_conduit_id': lambda ctx: ctx['object'].pk},
            ),
            ObjectsTablePanel(
                model='netbox_pathways.CableSegment',
                title='Cable Segments',
                filters={'pathway_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


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
    queryset = models.AerialSpan.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location',
    )
    table = tables.AerialSpanTable
    filterset = filters.AerialSpanFilterSet


class AerialSpanView(generic.ObjectView):
    queryset = models.AerialSpan.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.AerialSpanPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.CableSegment',
                title='Cable Segments',
                filters={'pathway_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


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
    queryset = models.DirectBuried.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location',
    )
    table = tables.DirectBuriedTable
    filterset = filters.DirectBuriedFilterSet


class DirectBuriedView(generic.ObjectView):
    queryset = models.DirectBuried.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.DirectBuriedPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.CableSegment',
                title='Cable Segments',
                filters={'pathway_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


class DirectBuriedEditView(generic.ObjectEditView):
    queryset = models.DirectBuried.objects.all()
    form = forms.DirectBuriedForm


class DirectBuriedDeleteView(generic.ObjectDeleteView):
    queryset = models.DirectBuried.objects.all()


# --- Innerduct ---

class InnerductListView(generic.ObjectListView):
    queryset = models.Innerduct.objects.select_related('parent_conduit')
    table = tables.InnerductTable
    filterset = filters.InnerductFilterSet


class InnerductView(generic.ObjectView):
    queryset = models.Innerduct.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.InnerductPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.CableSegment',
                title='Cable Segments',
                filters={'pathway_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


class InnerductEditView(generic.ObjectEditView):
    queryset = models.Innerduct.objects.all()
    form = forms.InnerductForm


class InnerductDeleteView(generic.ObjectDeleteView):
    queryset = models.Innerduct.objects.all()


# --- Conduit Bank ---

class ConduitBankListView(generic.ObjectListView):
    queryset = models.ConduitBank.objects.select_related('structure').annotate(
        conduit_count=Count('conduits'),
    )
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet


class ConduitBankView(generic.ObjectView):
    queryset = models.ConduitBank.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.ConduitBankPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        bottom_panels=[
            ObjectsTablePanel(
                model='netbox_pathways.Conduit',
                title='Conduits',
                filters={'conduit_bank_id': lambda ctx: ctx['object'].pk},
            ),
        ],
    )


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
    queryset = models.ConduitJunction.objects.select_related(
        'trunk_conduit', 'branch_conduit', 'towards_structure',
    )
    table = tables.ConduitJunctionTable
    filterset = filters.ConduitJunctionFilterSet


class ConduitJunctionView(generic.ObjectView):
    queryset = models.ConduitJunction.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.ConduitJunctionPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class ConduitJunctionEditView(generic.ObjectEditView):
    queryset = models.ConduitJunction.objects.all()
    form = forms.ConduitJunctionForm


class ConduitJunctionDeleteView(generic.ObjectDeleteView):
    queryset = models.ConduitJunction.objects.all()


# --- Cable Segment ---

class CableSegmentListView(generic.ObjectListView):
    queryset = models.CableSegment.objects.select_related('cable', 'pathway')
    table = tables.CableSegmentTable
    filterset = filters.CableSegmentFilterSet


class CableSegmentView(generic.ObjectView):
    queryset = models.CableSegment.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.CableSegmentPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


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


# --- Pathway Location ---

class PathwayLocationListView(generic.ObjectListView):
    queryset = models.PathwayLocation.objects.select_related('pathway', 'site', 'location')
    table = tables.PathwayLocationTable
    filterset = filters.PathwayLocationFilterSet


class PathwayLocationView(generic.ObjectView):
    queryset = models.PathwayLocation.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.PathwayLocationPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class PathwayLocationEditView(generic.ObjectEditView):
    queryset = models.PathwayLocation.objects.all()
    form = forms.PathwayLocationForm


class PathwayLocationDeleteView(generic.ObjectDeleteView):
    queryset = models.PathwayLocation.objects.all()


# --- Map View ---

MAP_MAX_OBJECTS = 2000


class MapView(generic.ObjectListView):
    queryset = models.Structure.objects.all()
    template_name = 'netbox_pathways/map.html'

    def _safe_float(self, value, default):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _safe_int(self, value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def get_extra_context(self, request):
        structures = models.Structure.objects.select_related('site')[:MAP_MAX_OBJECTS]
        pathways = models.Pathway.objects.select_related(
            'start_structure', 'end_structure',
        )[:MAP_MAX_OBJECTS]

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
            'map_center_lat': self._safe_float(request.GET.get('lat'), 45.5017),
            'map_center_lon': self._safe_float(request.GET.get('lon'), -73.5673),
            'map_zoom': self._safe_int(request.GET.get('zoom'), 10),
        }


# --- Pull Sheet ---

class PullSheetListView(generic.ObjectListView):
    """Lists cables that have pathway segments routed, for pull sheet selection."""
    queryset = Cable.objects.filter(
        pathway_segments__isnull=False,
    ).distinct().annotate(
        segment_count=Count('pathway_segments'),
    )
    table = tables.PullSheetCableTable
    template_name = 'netbox_pathways/pullsheet_list.html'

    def get_extra_context(self, request):
        return {'title': 'Pull Sheets'}


class PullSheetDetailView(LoginRequiredMixin, View):
    """Renders a pull sheet for a specific cable."""

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        segments = (
            models.CableSegment.objects
            .filter(cable=cable)
            .select_related(
                'pathway',
                'pathway__start_structure',
                'pathway__end_structure',
                'pathway__start_location',
                'pathway__end_location',
            )
            .order_by('sequence')
        )

        totals = segments.aggregate(
            total_pathway_length=Sum('pathway__length'),
            total_slack=Sum('slack_length'),
        )

        return render(request, 'netbox_pathways/pullsheet_detail.html', {
            'cable': cable,
            'segments': segments,
            'segment_count': segments.count(),
            'total_pathway_length': totals['total_pathway_length'] or 0,
            'total_slack': totals['total_slack'] or 0,
        })
