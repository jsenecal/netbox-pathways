from dcim.models import Cable, Site
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views import View
from extras.ui.panels import CustomFieldsPanel, TagsPanel
from netbox.ui import layout
from netbox.ui.panels import CommentsPanel, ObjectsTablePanel
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from netbox_pathways.registry import registry as map_layer_registry

from . import filters, forms, models, tables
from .graph import PathwayGraph, batch_resolve_nodes
from .ui import panels

# --- Structure ---

class StructureListView(generic.ObjectListView):
    queryset = models.Structure.objects.select_related('site', 'tenant')
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
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
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
        'start_structure', 'end_structure', 'start_location', 'end_location',
        'conduit_bank', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
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
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
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
        'start_structure', 'end_structure', 'start_location', 'end_location', 'tenant',
    ).annotate(cables_routed=Count('cable_segments'))
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
    queryset = models.Innerduct.objects.select_related('parent_conduit').annotate(
        cables_routed=Count('cable_segments'),
    )
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
    queryset = models.ConduitBank.objects.select_related('structure', 'tenant').annotate(
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


# --- Site Geometry ---

class SiteGeometryListView(generic.ObjectListView):
    queryset = models.SiteGeometry.objects.select_related('site', 'structure')
    table = tables.SiteGeometryTable
    filterset = filters.SiteGeometryFilterSet


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

        if request.GET.get('lat') or request.GET.get('lon'):
            ctx['map_center_lat'] = self._safe_float(request.GET.get('lat'), default_lat)
            ctx['map_center_lon'] = self._safe_float(request.GET.get('lon'), default_lon)
            ctx['map_zoom'] = self._safe_int(request.GET.get('zoom'), default_zoom)
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


# --- Graph Traversal Views ---

class RouteFinderView(LoginRequiredMixin, View):
    """UI for finding routes between two structures."""

    def get(self, request):
        start_id = request.GET.get('start')
        end_id = request.GET.get('end')
        mode = request.GET.get('mode', 'shortest')
        site_id = request.GET.get('site')

        context = {
            'structures': models.Structure.objects.order_by('name'),
            'start_id': None,
            'end_id': None,
            'mode': mode,
            'routes': None,
            'geo_data': None,
        }

        if not start_id or not end_id:
            return render(request, 'netbox_pathways/route_finder.html', context)

        try:
            start_id = int(start_id)
            end_id = int(end_id)
        except (TypeError, ValueError):
            return render(request, 'netbox_pathways/route_finder.html', context)

        context['start_id'] = start_id
        context['end_id'] = end_id

        site_id_int = None
        if site_id:
            try:
                site_id_int = int(site_id)
            except (TypeError, ValueError):
                pass

        graph = PathwayGraph.build(site_id=site_id_int)
        start_node = ('structure', start_id)
        end_node = ('structure', end_id)

        routes = []
        if mode == 'all':
            raw_routes = graph.all_routes(start_node, end_node, max_depth=20, max_routes=10)
            for cost, pw_ids in raw_routes:
                routes.append({
                    'total_length': round(cost, 2),
                    'hop_count': len(pw_ids),
                    'pathways': [graph.pathways[pid] for pid in pw_ids],
                })
        else:
            result = graph.shortest_path(start_node, end_node)
            if result:
                cost, pw_ids = result
                routes.append({
                    'total_length': round(cost, 2),
                    'hop_count': len(pw_ids),
                    'pathways': [graph.pathways[pid] for pid in pw_ids],
                })

        context['routes'] = routes

        # Build geo data for map
        geo_data = {'points': [], 'lines': []}

        # Start/end markers (batch-resolved)
        resolved = batch_resolve_nodes([start_node, end_node])
        start_info = resolved[start_node]
        end_info = resolved[end_node]
        if start_info['geo']:
            geo_data['points'].append({
                'lat': start_info['geo'][0], 'lon': start_info['geo'][1],
                'name': start_info['label'], 'color': 'green',
            })
        if end_info['geo']:
            geo_data['points'].append({
                'lat': end_info['geo'][0], 'lon': end_info['geo'][1],
                'name': end_info['label'], 'color': 'red',
            })

        # Show first (shortest) route on map
        route_colors = ['#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
                        '#42d4f4', '#f032e6', '#bfef45', '#fabebe', '#469990']
        for i, route in enumerate(routes):
            color = route_colors[i % len(route_colors)]
            for pw in route['pathways']:
                if pw['coords']:
                    geo_data['lines'].append({
                        'coords': pw['coords'],
                        'name': pw['name'],
                        'color': color,
                        'url': pw['url'],
                    })

        context['geo_data'] = geo_data
        return render(request, 'netbox_pathways/route_finder.html', context)



class NeighborsView(LoginRequiredMixin, View):
    """UI for exploring structure connectivity / neighbors."""

    def get(self, request):
        structure_id = request.GET.get('structure')
        max_hops = request.GET.get('max_hops', '3')
        site_id = request.GET.get('site')

        try:
            max_hops = min(int(max_hops), 10)
        except (TypeError, ValueError):
            max_hops = 3

        context = {
            'structures': models.Structure.objects.order_by('name'),
            'structure_id': None,
            'max_hops': max_hops,
            'neighbors': None,
            'geo_data': None,
        }

        if not structure_id:
            return render(request, 'netbox_pathways/neighbors.html', context)

        try:
            structure_id = int(structure_id)
        except (TypeError, ValueError):
            return render(request, 'netbox_pathways/neighbors.html', context)

        context['structure_id'] = structure_id

        site_id_int = None
        if site_id:
            try:
                site_id_int = int(site_id)
            except (TypeError, ValueError):
                pass

        graph = PathwayGraph.build(site_id=site_id_int)
        start_node = ('structure', structure_id)
        raw_neighbors = graph.neighbors(start_node, max_hops=max_hops)

        # Batch-resolve all nodes (start + neighbors) in one round-trip
        all_nodes = [start_node] + list(raw_neighbors.keys())
        resolved = batch_resolve_nodes(all_nodes)

        neighbor_list = []
        for node, (dist, hops, _pw_ids) in sorted(raw_neighbors.items(), key=lambda x: x[1][1]):
            info = resolved[node]
            neighbor_list.append({
                'type': node[0],
                'id': node[1],
                'label': info['label'],
                'distance': round(dist, 2),
                'hops': hops,
                'lat': info['geo'][0] if info['geo'] else None,
                'lon': info['geo'][1] if info['geo'] else None,
            })

        context['neighbors'] = neighbor_list

        # Build geo data
        geo_data = {'points': [], 'lines': []}

        # Origin marker
        start_info = resolved[start_node]
        if start_info['geo']:
            geo_data['points'].append({
                'lat': start_info['geo'][0], 'lon': start_info['geo'][1],
                'name': start_info['label'], 'color': 'red',
            })

        # Neighbor markers
        hop_colors = ['green', 'blue', 'orange', 'purple', 'cyan',
                      'pink', 'brown', 'gray', 'teal', 'indigo']
        for n in neighbor_list:
            if n['lat'] is not None:
                geo_data['points'].append({
                    'lat': n['lat'], 'lon': n['lon'],
                    'name': n['label'],
                    'color': hop_colors[(n['hops'] - 1) % len(hop_colors)],
                })

        # All pathways in the graph as context lines
        for pw_data in graph.pathways.values():
            if pw_data['coords']:
                geo_data['lines'].append({
                    'coords': pw_data['coords'],
                    'name': pw_data['name'],
                    'color': '#999',
                    'url': pw_data['url'],
                })

        context['geo_data'] = geo_data
        return render(request, 'netbox_pathways/neighbors.html', context)
