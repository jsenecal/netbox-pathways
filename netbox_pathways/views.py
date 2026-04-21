from dcim.models import Cable, Site
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.text import slugify
from django.views import View
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.object_actions import CloneObject, DeleteObject, EditObject, ObjectAction
from netbox.ui import layout
from netbox.ui.panels import CommentsPanel, ObjectsTablePanel, TemplatePanel
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from netbox_pathways.registry import registry as map_layer_registry

from . import filterforms, filters, forms, models, tables
from .graph import PathwayGraph, _endpoint_nodes, node_to_label
from .ui import panels


def _map_url_for(obj):
    """Build a map URL that centres on and selects this object."""
    if hasattr(obj, 'pathway_type') and obj.pathway_type:
        feature_type = obj.pathway_type
    else:
        feature_type = 'structure'
    return reverse('plugins:netbox_pathways:map') + f'?select={feature_type}-{obj.pk}'


class ViewInMap(ObjectAction):
    label = 'Map'
    template_name = 'netbox_pathways/buttons/view_in_map.html'

    @classmethod
    def get_url(cls, obj):
        return _map_url_for(obj)


# --- Structure ---

class StructureListView(generic.ObjectListView):
    queryset = models.Structure.objects.select_related('site', 'tenant')
    table = tables.StructureTable
    filterset = filters.StructureFilterSet
    filterset_form = filterforms.StructureFilterForm


class StructureView(generic.ObjectView):
    queryset = models.Structure.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
    layout = layout.SimpleLayout(
        left_panels=[
            panels.StructurePanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        right_panels=[],
        bottom_panels=[
            TemplatePanel(
                template_name='netbox_pathways/inc/connected_structures_panel.html',
            ),
        ],
    )

    def get_extra_context(self, request, instance):
        # Find all structures directly connected via any pathway
        connected_ids = set()
        pathways = models.Pathway.objects.filter(
            Q(start_structure=instance) | Q(end_structure=instance)
        ).select_related('start_structure', 'end_structure')
        for p in pathways:
            if p.start_structure_id and p.start_structure_id != instance.pk:
                connected_ids.add(p.start_structure_id)
            if p.end_structure_id and p.end_structure_id != instance.pk:
                connected_ids.add(p.end_structure_id)

        connected_qs = models.Structure.objects.filter(pk__in=connected_ids).select_related('site', 'tenant')
        table = tables.StructureTable(connected_qs, orderable=False)
        table.columns.hide('actions')
        table.columns.hide('pk')

        return {
            'connected_structures_table': table,
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


class StructureCreateSiteView(LoginRequiredMixin, View):
    """Create a NetBox Site from a Structure and link them."""

    def post(self, request, pk):
        if not request.user.has_perm('dcim.add_site'):
            messages.error(request, "You do not have permission to create sites.")
            return redirect('plugins:netbox_pathways:structure', pk=pk)

        structure = get_object_or_404(models.Structure, pk=pk)

        if structure.site:
            messages.warning(request, f"Structure already has a linked site: {structure.site}")
            return redirect(structure.get_absolute_url())

        # Generate a unique slug
        base_slug = slugify(structure.name)[:100]
        slug = base_slug
        counter = 2
        while Site.objects.filter(slug=slug).exists():
            suffix = f"-{counter}"
            slug = base_slug[: 100 - len(suffix)] + suffix
            counter += 1

        # Handle duplicate site names
        name = structure.name[:100]
        if Site.objects.filter(name=name).exists():
            messages.error(
                request,
                f'A site named "{name}" already exists. Create the site manually with a different name.',
            )
            return redirect(structure.get_absolute_url())

        site = Site.objects.create(
            name=name,
            slug=slug,
            status='active',
            tenant=structure.tenant,
        )
        structure.site = site
        structure.save()

        messages.success(request, f'Created site "{site.name}" and linked it to this structure.')
        return redirect(structure.get_absolute_url())


@register_model_view(models.Structure, 'conduit_banks')
class StructureConduitBanksView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.ConduitBank
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet
    tab = ViewTab(
        label='Conduit Banks',
        badge=lambda obj: models.ConduitBank.objects.filter(
            Q(start_structure=obj) | Q(end_structure=obj)
        ).count(),
    )

    def get_children(self, request, parent):
        return models.ConduitBank.objects.filter(
            Q(start_structure=parent) | Q(end_structure=parent)
        ).annotate(conduit_count=Count('conduits'))


@register_model_view(models.Structure, 'conduits')
class StructureConduitsView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.Conduit
    table = tables.ConduitTable
    filterset = filters.ConduitFilterSet
    tab = ViewTab(
        label='Conduits',
        badge=lambda obj: models.Conduit.objects.filter(
            Q(start_structure=obj) | Q(end_structure=obj)
        ).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return models.Conduit.objects.filter(
            Q(start_structure=parent) | Q(end_structure=parent)
        ).annotate(
            cables_routed=Count('cable_segments'),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
        )


@register_model_view(models.Structure, 'aerial_spans')
class StructureAerialSpansView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.AerialSpan
    table = tables.AerialSpanTable
    filterset = filters.AerialSpanFilterSet
    tab = ViewTab(
        label='Aerial Spans',
        badge=lambda obj: models.AerialSpan.objects.filter(
            Q(start_structure=obj) | Q(end_structure=obj)
        ).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return models.AerialSpan.objects.filter(
            Q(start_structure=parent) | Q(end_structure=parent)
        ).annotate(
            cables_routed=Count('cable_segments'),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
        )


@register_model_view(models.Structure, 'direct_buried')
class StructureDirectBuriedView(generic.ObjectChildrenView):
    queryset = models.Structure.objects.all()
    child_model = models.DirectBuried
    table = tables.DirectBuriedTable
    filterset = filters.DirectBuriedFilterSet
    tab = ViewTab(
        label='Direct Buried',
        badge=lambda obj: models.DirectBuried.objects.filter(
            Q(start_structure=obj) | Q(end_structure=obj)
        ).count(),
        hide_if_empty=True,
    )

    def get_children(self, request, parent):
        return models.DirectBuried.objects.filter(
            Q(start_structure=parent) | Q(end_structure=parent)
        ).annotate(
            cables_routed=Count('cable_segments'),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
        )


# --- Pathway (base) ---

class PathwayListView(generic.ObjectListView):
    queryset = models.Pathway.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(
        cables_routed=Count('cable_segments'),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
    )
    table = tables.PathwayTable
    filterset = filters.PathwayFilterSet
    filterset_form = filterforms.PathwayFilterForm


class PathwayView(generic.ObjectView):
    queryset = models.Pathway.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
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
        'start_structure', 'end_structure', 'start_location', 'end_location',
        'conduit_bank', 'tenant',
    ).annotate(
        cables_routed=Count('cable_segments'),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
    )
    table = tables.ConduitTable
    filterset_form = filterforms.ConduitFilterForm
    filterset = filters.ConduitFilterSet


class ConduitView(generic.ObjectView):
    queryset = models.Conduit.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
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
        return parent.innerducts.annotate(
            cables_routed=Count('cable_segments'),
            in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
        )


# --- Aerial Span ---

class AerialSpanListView(generic.ObjectListView):
    queryset = models.AerialSpan.objects.select_related(
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(
        cables_routed=Count('cable_segments'),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
    )
    table = tables.AerialSpanTable
    filterset = filters.AerialSpanFilterSet
    filterset_form = filterforms.AerialSpanFilterForm


class AerialSpanView(generic.ObjectView):
    queryset = models.AerialSpan.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
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
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(
        cables_routed=Count('cable_segments'),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
    )
    table = tables.DirectBuriedTable
    filterset = filters.DirectBuriedFilterSet
    filterset_form = filterforms.DirectBuriedFilterForm


class DirectBuriedView(generic.ObjectView):
    queryset = models.DirectBuried.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
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
    queryset = models.Innerduct.objects.select_related('parent_conduit').annotate(
        cables_routed=Count('cable_segments'),
        in_use=Exists(models.CableSegment.objects.filter(pathway=OuterRef('pk'))),
    )
    table = tables.InnerductTable
    filterset = filters.InnerductFilterSet
    filterset_form = filterforms.InnerductFilterForm


class InnerductView(generic.ObjectView):
    queryset = models.Innerduct.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
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
    queryset = models.ConduitBank.objects.select_related('start_structure', 'end_structure', 'tenant').annotate(
        conduit_count=Count('conduits'),
    )
    table = tables.ConduitBankTable
    filterset = filters.ConduitBankFilterSet
    filterset_form = filterforms.ConduitBankFilterForm


class ConduitBankView(generic.ObjectView):
    queryset = models.ConduitBank.objects.all()
    actions = (ViewInMap, CloneObject, EditObject, DeleteObject)
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
    queryset = models.ConduitBank.objects.annotate(conduit_count=Count('conduits'))
    filterset = filters.ConduitBankFilterSet
    table = tables.ConduitBankTable
    form = forms.ConduitBankBulkEditForm


class ConduitBankBulkDeleteView(generic.BulkDeleteView):
    queryset = models.ConduitBank.objects.annotate(conduit_count=Count('conduits'))
    table = tables.ConduitBankTable


# --- Conduit Junction ---

class ConduitJunctionListView(generic.ObjectListView):
    queryset = models.ConduitJunction.objects.select_related(
        'trunk_conduit', 'branch_conduit', 'towards_structure',
    )
    table = tables.ConduitJunctionTable
    filterset = filters.ConduitJunctionFilterSet
    filterset_form = filterforms.ConduitJunctionFilterForm


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
    filterset_form = filterforms.CableSegmentFilterForm


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

    def get_extra_context(self, request, instance):
        ctx = super().get_extra_context(request, instance)
        siblings = list(
            models.CableSegment.objects.filter(cable=instance.cable)
            .select_related('pathway')
            .order_by('sequence')
        )
        current_idx = next(
            (i for i, s in enumerate(siblings) if s.pk == instance.pk), 0
        )
        ctx['prev_segment'] = siblings[current_idx - 1] if current_idx > 0 else None
        ctx['next_segment'] = siblings[current_idx + 1] if current_idx < len(siblings) - 1 else None
        ctx['segment_ordinal'] = current_idx + 1
        ctx['segment_total'] = len(siblings)
        return ctx


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
    filterset_form = filterforms.PathwayLocationFilterForm


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


# --- Site Geometry ---

class SiteGeometryListView(generic.ObjectListView):
    queryset = models.SiteGeometry.objects.select_related('site', 'structure')
    table = tables.SiteGeometryTable
    filterset = filters.SiteGeometryFilterSet
    filterset_form = filterforms.SiteGeometryFilterForm


class SiteGeometryView(generic.ObjectView):
    queryset = models.SiteGeometry.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.SiteGeometryPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class SiteGeometryEditView(generic.ObjectEditView):
    queryset = models.SiteGeometry.objects.all()
    form = forms.SiteGeometryForm


class SiteGeometryDeleteView(generic.ObjectDeleteView):
    queryset = models.SiteGeometry.objects.all()


# --- Circuit Geometry ---

class CircuitGeometryListView(generic.ObjectListView):
    queryset = models.CircuitGeometry.objects.select_related(
        'circuit', 'circuit__provider',
    )
    table = tables.CircuitGeometryTable
    filterset = filters.CircuitGeometryFilterSet
    filterset_form = filterforms.CircuitGeometryFilterForm


class CircuitGeometryView(generic.ObjectView):
    queryset = models.CircuitGeometry.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.CircuitGeometryPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
    )


class CircuitGeometryEditView(generic.ObjectEditView):
    queryset = models.CircuitGeometry.objects.all()
    form = forms.CircuitGeometryForm


class CircuitGeometryDeleteView(generic.ObjectDeleteView):
    queryset = models.CircuitGeometry.objects.all()


# --- Slack Loops ---

class SlackLoopListView(generic.ObjectListView):
    queryset = models.SlackLoop.objects.select_related('cable', 'structure', 'pathway')
    table = tables.SlackLoopTable
    filterset = filters.SlackLoopFilterSet
    filterset_form = filterforms.SlackLoopFilterForm


class SlackLoopView(generic.ObjectView):
    queryset = models.SlackLoop.objects.all()
    layout = layout.SimpleLayout(
        left_panels=[
            panels.SlackLoopPanel(),
            TagsPanel(),
            CustomFieldsPanel(),
            CommentsPanel(),
        ],
        right_panels=[],
    )


class SlackLoopEditView(generic.ObjectEditView):
    queryset = models.SlackLoop.objects.all()
    form = forms.SlackLoopForm


class SlackLoopDeleteView(generic.ObjectDeleteView):
    queryset = models.SlackLoop.objects.all()


class SlackLoopBulkDeleteView(generic.BulkDeleteView):
    queryset = models.SlackLoop.objects.all()
    table = tables.SlackLoopTable


# --- Map View ---


class MapView(LoginRequiredMixin, View):
    """Full-page infrastructure map. Data is fetched client-side from GeoJSON API."""

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

    def _data_extent(self):
        """Compute WGS84 bounding box of all structures + pathways.

        Uses a two-pass approach for structures: first compute a rough
        centroid, then re-compute the extent excluding points that are
        far from the median (> 2 degrees), which filters GPS outliers.
        """
        from django.db import connection

        bbox = None

        with connection.cursor() as cursor:
            # Structures — trimmed extent to reject outliers
            cursor.execute("""
                WITH pts AS (
                    SELECT ST_Transform(location, 4326) AS geom
                    FROM netbox_pathways_structure
                    WHERE location IS NOT NULL
                ),
                med AS (
                    SELECT ST_Y(ST_Centroid(ST_Collect(geom))) AS lat,
                           ST_X(ST_Centroid(ST_Collect(geom))) AS lon
                    FROM pts
                ),
                trimmed AS (
                    SELECT pts.geom FROM pts, med
                    WHERE abs(ST_Y(pts.geom) - med.lat) < 2
                      AND abs(ST_X(pts.geom) - med.lon) < 2
                )
                SELECT ST_Extent(geom) FROM trimmed
            """)
            row = cursor.fetchone()
            if row and row[0]:
                # Parse BOX(xmin ymin,xmax ymax)
                bbox = self._parse_box(row[0])

            # Pathways
            cursor.execute("""
                SELECT ST_Extent(ST_Transform(path, 4326))
                FROM netbox_pathways_pathway
                WHERE path IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[0]:
                pbox = self._parse_box(row[0])
                if pbox:
                    if bbox:
                        bbox = (
                            min(bbox[0], pbox[0]),
                            min(bbox[1], pbox[1]),
                            max(bbox[2], pbox[2]),
                            max(bbox[3], pbox[3]),
                        )
                    else:
                        bbox = pbox

        return bbox  # (west, south, east, north) or None

    @staticmethod
    def _parse_box(box_str):
        """Parse PostGIS BOX(xmin ymin,xmax ymax) to (west, south, east, north)."""
        try:
            coords = box_str.replace('BOX(', '').replace(')', '')
            min_part, max_part = coords.split(',')
            west, south = (float(v) for v in min_part.split())
            east, north = (float(v) for v in max_part.split())
            return (west, south, east, north)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _resolve_feature_extent(select_param):
        """Resolve WGS84 bounding box from a select param like 'structure-123'.

        Returns (west, south, east, north) or None.
        """
        from django.contrib.gis.db.models import Extent
        from django.contrib.gis.db.models.functions import Transform

        try:
            ftype, fid = select_param.rsplit('-', 1)
            fid = int(fid)
        except (ValueError, AttributeError):
            return None

        model_map = {
            'structure': (models.Structure, 'location'),
            'conduit': (models.Conduit, 'path'),
            'conduit_bank': (models.ConduitBank, 'path'),
            'aerial': (models.AerialSpan, 'path'),
            'direct_buried': (models.DirectBuried, 'path'),
        }
        entry = model_map.get(ftype)
        if not entry:
            return None

        model_cls, geom_field = entry
        try:
            result = model_cls.objects.filter(pk=fid).annotate(
                _geo=Transform(geom_field, 4326),
            ).aggregate(bbox=Extent('_geo'))
            bbox = result.get('bbox')
            if bbox:
                return bbox  # (west, south, east, north)
        except Exception:
            pass
        return None

    def get(self, request):
        import json

        from django.conf import settings
        plugin_cfg = settings.PLUGINS_CONFIG.get('netbox_pathways', {})

        api_base = reverse('plugins-api:netbox_pathways-api:api-root')
        geo_base = f'{api_base}geo/'

        pathways_config = {
            'maxNativeZoom': plugin_cfg.get('map_max_native_zoom', 19),
            'apiBase': geo_base,
            'overlays': plugin_cfg.get('map_overlays', []),
            'baseLayers': plugin_cfg.get('map_base_layers', []),
            'externalLayers': [
                layer.to_json(api_base=geo_base)
                for layer in map_layer_registry.all()
            ],
        }

        # Compute extent from data; fall back to config or defaults
        extent = self._data_extent()
        default_lat = plugin_cfg.get('map_center_lat', 45.5017)
        default_lon = plugin_cfg.get('map_center_lon', -73.5673)
        default_zoom = plugin_cfg.get('map_zoom', 10)

        ctx = {
            'pathways_config_json': json.dumps(pathways_config),
        }

        ctx['kiosk'] = request.GET.get('kiosk', '').lower() == 'true'
        ctx['selected_feature'] = request.GET.get('select', '')

        if request.GET.get('lat') or request.GET.get('lon'):
            ctx['map_center_lat'] = self._safe_float(request.GET.get('lat'), default_lat)
            ctx['map_center_lon'] = self._safe_float(request.GET.get('lon'), default_lon)
            ctx['map_zoom'] = self._safe_int(request.GET.get('zoom'), default_zoom)
            ctx['map_bounds'] = ''
        elif ctx['selected_feature']:
            # Resolve bounds from the selected feature's geometry
            sel_ext = self._resolve_feature_extent(ctx['selected_feature'])
            if sel_ext:
                ctx['map_center_lat'] = (sel_ext[1] + sel_ext[3]) / 2
                ctx['map_center_lon'] = (sel_ext[0] + sel_ext[2]) / 2
                ctx['map_zoom'] = 18  # fallback if fitBounds not used
                ctx['map_bounds'] = json.dumps([
                    [sel_ext[1], sel_ext[0]],
                    [sel_ext[3], sel_ext[2]],
                ])
            elif extent:
                ctx['map_center_lat'] = (extent[1] + extent[3]) / 2
                ctx['map_center_lon'] = (extent[0] + extent[2]) / 2
                ctx['map_zoom'] = default_zoom
                ctx['map_bounds'] = json.dumps([
                    [extent[1], extent[0]],
                    [extent[3], extent[2]],
                ])
            else:
                ctx['map_center_lat'] = default_lat
                ctx['map_center_lon'] = default_lon
                ctx['map_zoom'] = default_zoom
                ctx['map_bounds'] = ''
        elif extent:
            ctx['map_center_lat'] = (extent[1] + extent[3]) / 2
            ctx['map_center_lon'] = (extent[0] + extent[2]) / 2
            ctx['map_zoom'] = default_zoom
            ctx['map_bounds'] = json.dumps([
                [extent[1], extent[0]],
                [extent[3], extent[2]],
            ])
        else:
            ctx['map_center_lat'] = default_lat
            ctx['map_center_lon'] = default_lon
            ctx['map_zoom'] = default_zoom
            ctx['map_bounds'] = ''

        return render(request, 'netbox_pathways/map.html', ctx)


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
        from .routing import validate_cable_route

        cable = get_object_or_404(Cable, pk=cable_pk)
        route = validate_cable_route(cable.pk)

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
        )

        # Slack from SlackLoop model
        slack_loops = models.SlackLoop.objects.filter(
            cable=cable,
        ).select_related('structure', 'pathway')
        total_slack = slack_loops.aggregate(total=Sum('length'))['total'] or 0

        return render(request, 'netbox_pathways/pullsheet_detail.html', {
            'cable': cable,
            'segments': segments,
            'segment_count': segments.count(),
            'total_pathway_length': totals['total_pathway_length'] or 0,
            'route': route,
            'slack_loops': slack_loops,
            'total_slack': total_slack,
        })


class AdjacencyView(LoginRequiredMixin, View):
    """Return pathways connected to a given node as JSON."""

    def get(self, request):
        node_type = request.GET.get('node_type')
        node_id = request.GET.get('node_id')
        if not node_type or not node_id:
            return JsonResponse(
                {'error': 'node_type and node_id are required'}, status=400,
            )
        try:
            node_id = int(node_id)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'node_id must be an integer'}, status=400)

        node = (node_type, node_id)
        graph = PathwayGraph.build()
        connected = graph.connected_pathways(node)

        results = []
        for edge in connected:
            pw_info = graph.pathways.get(edge['pathway_id'], {})
            dest_label = node_to_label(edge['destination'])
            results.append({
                'pathway_id': edge['pathway_id'],
                'label': pw_info.get('name', ''),
                'destination': dest_label,
                'length': edge['weight'],
                'pathway_type': edge['pathway_type'],
            })

        return JsonResponse(results, safe=False)


# --- Cable Routing Panel HTMX Views ---


class CableRoutingMixin:
    """Shared helpers for routing panel views."""

    def _start_node(self, cable):
        """Resolve A termination to a graph node."""
        from dcim.models import CableTermination
        term = CableTermination.objects.filter(
            cable=cable, cable_end='A',
        ).select_related('_site').first()
        if not term or not term._site_id:
            return None
        structures = models.Structure.objects.filter(site_id=term._site_id)
        if structures.count() == 1:
            return ('structure', structures.first().pk)
        first = structures.first()
        return ('structure', first.pk) if first else None

    def _end_node(self, cable):
        """Resolve B termination to a graph node."""
        from dcim.models import CableTermination
        term = CableTermination.objects.filter(
            cable=cable, cable_end='B',
        ).select_related('_site').first()
        if not term or not term._site_id:
            return None
        structures = models.Structure.objects.filter(site_id=term._site_id)
        if structures.count() == 1:
            return ('structure', structures.first().pk)
        first = structures.first()
        return ('structure', first.pk) if first else None

    def _far_end_node(self, pathway, coming_from_node=None):
        """Return the opposite end of a pathway from the entry node."""
        start, end = _endpoint_nodes(pathway)
        if coming_from_node and coming_from_node == end:
            return start
        return end

    def _render_table(self, request, cable):
        segments = list(
            models.CableSegment.objects.filter(cable=cable)
            .select_related(
                'pathway', 'pathway__start_structure', 'pathway__end_structure',
                'pathway__start_location', 'pathway__end_location',
            )
            .order_by('sequence')
        )
        for i, seg in enumerate(segments):
            seg.ordinal = i + 1
            seg.gap_before = (i > 0 and seg.sequence != segments[i - 1].sequence + 1)
            seg.prev_sequence = segments[i - 1].sequence if i > 0 else 0
            seg.start_name = str(seg.pathway.start_endpoint) if seg.pathway and seg.pathway.start_endpoint else None
            seg.end_name = str(seg.pathway.end_endpoint) if seg.pathway and seg.pathway.end_endpoint else None

        html = render_to_string(
            'netbox_pathways/inc/cable_segment_table.html',
            {'cable': cable, 'segments': segments},
            request=request,
        )
        return HttpResponse(html)


class CableRoutingAddSegmentView(CableRoutingMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTMX: Show add-segment form or process segment creation."""
    permission_required = 'netbox_pathways.add_cablesegment'

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        after_sequence = request.GET.get('after_sequence')

        segments = list(
            models.CableSegment.objects.filter(cable=cable)
            .select_related('pathway')
            .order_by('sequence')
        )

        if after_sequence is not None:
            after_sequence = int(after_sequence)
            prev_seg = next((s for s in segments if s.sequence == after_sequence), None)
            if prev_seg and prev_seg.pathway:
                node = self._far_end_node(prev_seg.pathway)
            else:
                node = self._start_node(cable)
        elif segments:
            last = segments[-1]
            if last.pathway:
                node = self._far_end_node(last.pathway)
            else:
                node = self._start_node(cable)
        else:
            node = self._start_node(cable)

        graph = PathwayGraph.build()
        connected = graph.connected_pathways(node) if node else []
        pathway_ids = [c['pathway_id'] for c in connected]
        pathways = models.Pathway.objects.filter(pk__in=pathway_ids).select_related(
            'start_structure', 'end_structure',
        )

        choices = []
        for pw in pathways:
            dest = pw.end_endpoint or pw.start_endpoint
            length_str = f"{pw.length:.1f}m" if pw.length else "?"
            choices.append((pw.pk, f"{pw} \u2192 {dest} ({length_str})"))

        html = render_to_string(
            'netbox_pathways/inc/cable_add_segment_form.html',
            {
                'cable': cable,
                'choices': choices,
                'after_sequence': after_sequence,
            },
            request=request,
        )
        return HttpResponse(html)

    def post(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        pathway_id = request.POST.get('pathway')
        after_sequence = request.POST.get('after_sequence')

        pathway = get_object_or_404(models.Pathway, pk=pathway_id) if pathway_id else None

        if after_sequence:
            sequence = int(after_sequence) + 1
            with transaction.atomic():
                models.CableSegment.objects.filter(
                    cable=cable, sequence__gte=sequence,
                ).update(sequence=F('sequence') + 1)
                seg = models.CableSegment(cable=cable, pathway=pathway, sequence=sequence)
                seg.save()
        else:
            seg = models.CableSegment(cable=cable, pathway=pathway)
            seg.save()

        return self._render_table(request, cable)


class CableRoutingDeleteSegmentView(CableRoutingMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTMX: Delete a segment and return updated table."""
    permission_required = 'netbox_pathways.delete_cablesegment'

    def post(self, request, cable_pk, segment_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        seg = get_object_or_404(models.CableSegment, pk=segment_pk, cable=cable)
        seg.delete()
        return self._render_table(request, cable)


class CableRoutingFindRouteView(CableRoutingMixin, LoginRequiredMixin, View):
    """HTMX: Find routes between cable A/B terminations."""

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        start_node = self._start_node(cable)
        end_node = self._end_node(cable)

        routes = []
        if start_node and end_node:
            graph = PathwayGraph.build()
            routes = graph.all_routes(start_node, end_node, max_depth=20, max_routes=10)

        enriched_routes = []
        for cost, pathway_ids in routes:
            pathways = models.Pathway.objects.filter(
                pk__in=pathway_ids,
            ).select_related('start_structure', 'end_structure')
            pw_map = {pw.pk: pw for pw in pathways}
            enriched_routes.append({
                'cost': cost,
                'hop_count': len(pathway_ids),
                'pathways': [pw_map.get(pid) for pid in pathway_ids if pw_map.get(pid)],
                'pathway_ids': ','.join(str(pid) for pid in pathway_ids),
            })

        existing_count = models.CableSegment.objects.filter(cable=cable).count()

        html = render_to_string(
            'netbox_pathways/inc/cable_route_finder_results.html',
            {
                'cable': cable,
                'routes': enriched_routes,
                'existing_count': existing_count,
            },
            request=request,
        )
        return HttpResponse(html)


class CableRoutingApplyRouteView(CableRoutingMixin, LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTMX: Apply a found route -- create segments from pathway IDs."""
    permission_required = ('netbox_pathways.add_cablesegment', 'netbox_pathways.delete_cablesegment')

    def post(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        pathway_ids_str = request.POST.get('pathway_ids', '')
        pathway_ids = [int(pid) for pid in pathway_ids_str.split(',') if pid.strip()]

        with transaction.atomic():
            models.CableSegment.objects.filter(cable=cable).delete()
            for i, pw_id in enumerate(pathway_ids, start=1):
                seg = models.CableSegment(cable=cable, pathway_id=pw_id, sequence=i)
                seg.save()

        return self._render_table(request, cable)


class CableRoutingTableView(CableRoutingMixin, LoginRequiredMixin, View):
    """HTMX: Re-render the segment table (used by Cancel button)."""

    def get(self, request, cable_pk):
        cable = get_object_or_404(Cable, pk=cable_pk)
        return self._render_table(request, cable)
