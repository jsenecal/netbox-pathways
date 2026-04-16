from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from netbox.plugins.templates import PluginTemplateExtension

from . import models
from .geo import linestring_to_coords, point_to_latlon
from .routing import validate_cable_route


def _leaflet_head():
    """Return HTML to load Leaflet and django-leaflet assets in <head>."""
    css = [
        static('leaflet/leaflet.css'),
        static('leaflet/leaflet_django.css'),
        static('leaflet/leaflet.extras.css'),
        static('leaflet/draw/leaflet.draw.css'),
        static('netbox_pathways/vendor/MarkerCluster.css'),
        static('netbox_pathways/vendor/MarkerCluster.Default.css'),
        static('netbox_pathways/css/leaflet-theme.css'),
    ]
    js = [
        static('leaflet/leaflet.js'),
        static('leaflet/leaflet.extras.js'),
        static('leaflet/draw/leaflet.draw.js'),
        static('leaflet/leaflet.forms.js'),
        static('netbox_pathways/vendor/leaflet.markercluster.js'),
    ]
    html = ''
    for href in css:
        html += f'<link rel="stylesheet" href="{href}" />\n'
    for src in js:
        html += f'<script src="{src}"></script>\n'
    return html

PATHWAY_COLORS = {
    'conduit': 'brown',
    'aerial': 'blue',
    'direct_buried': 'gray',
    'innerduct': 'orange',
    'microduct': 'purple',
    'tray': 'green',
    'raceway': 'cyan',
    'submarine': 'navy',
}

STRUCTURE_COLORS = {
    'pole': 'green',
    'manhole': 'blue',
    'handhole': 'cyan',
    'cabinet': 'orange',
    'vault': 'purple',
    'pedestal': 'yellow',
    'building_entrance': 'red',
    'splice_closure': 'brown',
    'tower': 'darkred',
    'roof': 'gray',
    'equipment_room': 'teal',
    'telecom_closet': 'indigo',
    'riser_room': 'pink',
}


def _pathway_line(pathway):
    """Build a line dict from a Pathway instance."""
    if not pathway.path:
        return None
    return {
        'coords': linestring_to_coords(pathway.path),
        'name': str(pathway),
        'color': PATHWAY_COLORS.get(pathway.pathway_type, 'gray'),
        'url': pathway.get_absolute_url(),
    }


def _structure_point(structure, color=None):
    """Build a point dict from a Structure instance."""
    latlon = point_to_latlon(structure.centroid)
    if latlon is None:
        return None
    return {
        'lat': latlon[0],
        'lon': latlon[1],
        'name': structure.name,
        'structure_type': structure.get_structure_type_display(),
        'color': color or STRUCTURE_COLORS.get(structure.structure_type, 'gray'),
        'url': structure.get_absolute_url(),
    }


class LeafletHeadExtension(PluginTemplateExtension):
    """Load Leaflet + detail-map assets globally via {% plugin_head %}.

    NetBox's base template calls {% plugin_head %} without an object, so only
    extensions with models=None (global) are invoked.  Setting a models list
    here would silently prevent head() from ever being called.
    """

    def head(self):
        import json

        from django.conf import settings
        plugin_cfg = settings.PLUGINS_CONFIG.get('netbox_pathways', {})

        api_base = reverse('plugins-api:netbox_pathways-api:api-root')
        config = {
            'maxNativeZoom': plugin_cfg.get('map_max_native_zoom', 19),
            'apiBase': f'{api_base}geo/',
            'overlays': plugin_cfg.get('map_overlays', []),
            'baseLayers': plugin_cfg.get('map_base_layers', []),
        }

        detail_js = static('netbox_pathways/dist/detail-map.min.js')
        config_js = f'<script>window.PATHWAYS_CONFIG={json.dumps(config)};</script>\n'
        return _leaflet_head() + config_js + f'<script src="{detail_js}"></script>\n'


class PluginModelMapExtension(PluginTemplateExtension):
    """Map panel on plugin model detail pages (Structure, Pathway subtypes, etc.)."""

    models = [
        'netbox_pathways.structure',
        'netbox_pathways.pathway',
        'netbox_pathways.conduit',
        'netbox_pathways.aerialspan',
        'netbox_pathways.directburied',
        'netbox_pathways.innerduct',
        'netbox_pathways.conduitbank',
        'netbox_pathways.conduitjunction',
    ]

    def right_page(self):
        obj = self.context['object']
        geo_data = self._get_geo_data(obj)
        if not geo_data:
            return ''
        map_id = f'geo-{obj._meta.model_name}-{obj.pk}'
        return self.render('netbox_pathways/inc/geo_map_panel.html', extra_context={
            'geo_data': geo_data,
            'map_id': map_id,
            'data_id': f'{map_id}-data',
            'panel_title': 'Location',
        })

    def _get_geo_data(self, obj):
        data = {'points': [], 'lines': []}

        if isinstance(obj, models.Structure):
            pt = _structure_point(obj)
            if pt:
                data['points'].append(pt)

        elif isinstance(obj, models.ConduitBank):
            line = _pathway_line(obj)
            if line:
                data['lines'].append(line)
            for struct in (obj.start_structure, obj.end_structure):
                if struct:
                    pt = _structure_point(struct, color='orange')
                    if pt:
                        data['points'].append(pt)

        elif isinstance(obj, models.ConduitJunction):
            # Show the trunk conduit line for context
            if obj.trunk_conduit_id:
                line = _pathway_line(obj.trunk_conduit)
                if line:
                    data['lines'].append(line)
            # Show the computed junction point
            loc = obj.location
            if loc:
                data['points'].append({
                    'lat': loc.y,
                    'lon': loc.x,
                    'name': str(obj),
                    'color': 'red',
                })

        elif isinstance(obj, models.Pathway):
            # Pathway base or any MTI subtype (Conduit, AerialSpan, etc.)
            line = _pathway_line(obj)
            if line:
                data['lines'].append(line)
            # Start/end structure markers
            if obj.start_structure_id:
                latlon = point_to_latlon(obj.start_structure.centroid)
                if latlon:
                    data['points'].append({
                        'lat': latlon[0],
                        'lon': latlon[1],
                        'name': str(obj.start_structure),
                        'color': 'green',
                    })
            if obj.end_structure_id:
                latlon = point_to_latlon(obj.end_structure.centroid)
                if latlon:
                    data['points'].append({
                        'lat': latlon[0],
                        'lon': latlon[1],
                        'name': str(obj.end_structure),
                        'color': 'red',
                    })

        if not data['points'] and not data['lines']:
            return None
        return data


class CoreModelMapExtension(PluginTemplateExtension):
    """Infrastructure overview map on Site and Location detail pages."""

    models = ['dcim.site', 'dcim.location']

    def right_page(self):
        obj = self.context['object']
        geo_data = self._get_geo_data(obj)
        if not geo_data:
            return ''
        map_id = f'geo-{obj._meta.model_name}-{obj.pk}'
        return self.render('netbox_pathways/inc/geo_map_panel.html', extra_context={
            'geo_data': geo_data,
            'map_id': map_id,
            'data_id': f'{map_id}-data',
            'panel_title': 'Pathways Infrastructure',
            'dynamic_layers': 'true',
        })

    def _get_geo_data(self, obj):
        from dcim.models import Location, Site

        data = {'points': [], 'lines': []}

        if isinstance(obj, Site):
            # Show site boundary if present
            try:
                site_geo = models.SiteGeometry.objects.select_related('structure').get(site=obj)
                geom = site_geo.effective_geometry
                if geom:
                    from .geo import to_leaflet
                    geom = to_leaflet(geom)
                    if geom and geom.geom_type in ('Polygon', 'MultiPolygon'):
                        if geom.geom_type == 'Polygon':
                            coords = [[p[0], p[1]] for p in geom.exterior_ring.coords]
                        else:
                            coords = [[p[0], p[1]] for p in geom[0].exterior_ring.coords]
                        data['lines'].append({
                            'coords': coords,
                            'name': f'Site boundary: {obj.name}',
                            'color': '#333',
                        })
            except models.SiteGeometry.DoesNotExist:
                pass

            for s in models.Structure.objects.filter(site=obj).only(
                'name', 'structure_type', 'location',
            )[:500]:
                pt = _structure_point(s)
                if pt:
                    data['points'].append(pt)

            pathways = models.Pathway.objects.filter(
                Q(start_structure__site=obj) | Q(end_structure__site=obj),
            ).only(
                'name', 'pathway_type', 'path',
            )[:500]
            for p in pathways:
                line = _pathway_line(p)
                if line:
                    data['lines'].append(line)

        elif isinstance(obj, Location):
            pathways = models.Pathway.objects.filter(
                Q(start_location=obj) | Q(end_location=obj),
            ).select_related(
                'start_structure', 'end_structure',
            ).only(
                'name', 'pathway_type', 'path',
                'start_structure_id', 'end_structure_id',
                'start_structure__name', 'start_structure__structure_type',
                'start_structure__location',
                'end_structure__name', 'end_structure__structure_type',
                'end_structure__location',
            )[:500]
            for p in pathways:
                line = _pathway_line(p)
                if line:
                    data['lines'].append(line)
                # Also show endpoint structures
                if p.start_structure_id:
                    pt = _structure_point(p.start_structure)
                    if pt:
                        data['points'].append(pt)
                if p.end_structure_id:
                    pt = _structure_point(p.end_structure)
                    if pt:
                        data['points'].append(pt)

        if not data['points'] and not data['lines']:
            return None
        return data


class CableRouteStatusExtension(PluginTemplateExtension):
    """Route status panel on Cable detail pages."""

    models = ['dcim.cable']

    def left_page(self):
        from django.utils.html import format_html, mark_safe

        obj = self.context['object']
        route = validate_cable_route(obj.pk)

        if route['segment_count'] == 0:
            return ''

        # Build status badge
        if route['valid']:
            badge = '<span class="badge text-bg-green">Complete</span>'
            pullsheet_link = format_html(
                ' <a href="{}" class="btn btn-sm btn-outline-secondary ms-2">'
                '<i class="mdi mdi-file-document-outline"></i> Pull Sheet</a>',
                f'/plugins/pathways/pull-sheets/{obj.pk}/',
            )
        else:
            gap_count = len(route['gaps'])
            badge = f'<span class="badge text-bg-yellow">{gap_count} gap{"s" if gap_count != 1 else ""}</span>'
            pullsheet_link = ''

        # Build gap details
        gap_html = ''
        if route['gaps']:
            gap_rows = []
            for gap in route['gaps']:
                gap_rows.append(
                    f'<tr><td>{gap.get("after_pathway") or "—"}</td>'
                    f'<td>{gap.get("before_pathway") or "—"}</td>'
                    f'<td>{gap["detail"]}</td></tr>'
                )
            gap_html = (
                '<table class="table table-sm table-hover mt-2 mb-0">'
                '<thead><tr><th>After</th><th>Before</th><th>Detail</th></tr></thead>'
                '<tbody>' + ''.join(gap_rows) + '</tbody></table>'
            )

        html = format_html(
            '<div class="card mb-3">'
            '<div class="card-header"><h5 class="card-title mb-0">Route Status</h5></div>'
            '<div class="card-body">'
            '<div class="d-flex align-items-center">'
            '<span class="me-2">{} segment{}</span> {}{}'
            '</div>{}'
            '</div></div>',
            route['segment_count'],
            's' if route['segment_count'] != 1 else '',
            mark_safe(badge),
            mark_safe(pullsheet_link),
            mark_safe(gap_html),
        )
        return html


class CableSlackLoopExtension(PluginTemplateExtension):
    """Slack loops table on Cable detail pages."""

    models = ['dcim.cable']

    def left_page(self):
        obj = self.context['object']
        slack_loops = models.SlackLoop.objects.filter(cable=obj).select_related('structure', 'pathway')
        if not slack_loops.exists():
            return ''

        rows = []
        for sl in slack_loops:
            pw_name = str(sl.pathway) if sl.pathway else '—'
            rows.append(
                f'<tr>'
                f'<td><a href="{sl.structure.get_absolute_url()}">{sl.structure.name}</a></td>'
                f'<td>{pw_name}</td>'
                f'<td>{sl.length} m</td>'
                f'</tr>'
            )

        total = sum(sl.length for sl in slack_loops)

        from django.utils.html import format_html, mark_safe
        return format_html(
            '<div class="card mb-3">'
            '<div class="card-header"><h5 class="card-title mb-0">Slack Loops</h5></div>'
            '<div class="card-body p-0">'
            '<table class="table table-sm table-hover mb-0">'
            '<thead><tr><th>Structure</th><th>Pathway</th><th>Length</th></tr></thead>'
            '<tbody>{}</tbody>'
            '<tfoot><tr><td colspan="2"><strong>Total</strong></td><td><strong>{} m</strong></td></tr></tfoot>'
            '</table></div></div>',
            mark_safe(''.join(rows)),
            total,
        )


class StructureSlackLoopExtension(PluginTemplateExtension):
    """Slack loops table on Structure detail pages."""

    models = ['netbox_pathways.structure']

    def right_page(self):
        obj = self.context['object']
        slack_loops = models.SlackLoop.objects.filter(structure=obj).select_related('cable', 'pathway')
        if not slack_loops.exists():
            return ''

        rows = []
        for sl in slack_loops:
            pw_name = str(sl.pathway) if sl.pathway else '—'
            rows.append(
                f'<tr>'
                f'<td><a href="#">{sl.cable.label}</a></td>'
                f'<td>{pw_name}</td>'
                f'<td>{sl.length} m</td>'
                f'</tr>'
            )

        from django.utils.html import format_html, mark_safe
        return format_html(
            '<div class="card mb-3">'
            '<div class="card-header"><h5 class="card-title mb-0">Slack Loops</h5></div>'
            '<div class="card-body p-0">'
            '<table class="table table-sm table-hover mb-0">'
            '<thead><tr><th>Cable</th><th>Pathway</th><th>Length</th></tr></thead>'
            '<tbody>{}</tbody>'
            '</table></div></div>',
            mark_safe(''.join(rows)),
        )


class CableRouteMapExtension(PluginTemplateExtension):
    """Map panel on Cable detail pages showing pathway route."""

    models = ['dcim.cable']

    def right_page(self):
        obj = self.context['object']
        segments = models.CableSegment.objects.filter(
            cable=obj,
        ).select_related(
            'pathway',
            'pathway__start_structure',
            'pathway__end_structure',
        ).order_by('sequence')

        if not segments.exists():
            return ''

        segment_colors = [
            '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
            '#42d4f4', '#f032e6', '#bfef45', '#fabebe', '#469990',
        ]
        data = {'points': [], 'lines': []}
        for i, seg in enumerate(segments):
            pw = seg.pathway
            if pw and pw.path:
                data['lines'].append({
                    'coords': linestring_to_coords(pw.path),
                    'name': str(pw),
                    'color': segment_colors[i % len(segment_colors)],
                    'url': pw.get_absolute_url(),
                })
            if pw and pw.start_structure_id:
                pt = _structure_point(pw.start_structure, color='green')
                if pt:
                    data['points'].append(pt)
            if pw and pw.end_structure_id:
                pt = _structure_point(pw.end_structure, color='red')
                if pt:
                    data['points'].append(pt)

        if not data['points'] and not data['lines']:
            return ''

        map_id = f'geo-cable-{obj.pk}'
        return self.render('netbox_pathways/inc/geo_map_panel.html', extra_context={
            'geo_data': data,
            'map_id': map_id,
            'data_id': f'{map_id}-data',
            'panel_title': 'Pathway Route',
        })


template_extensions = [
    LeafletHeadExtension,
    PluginModelMapExtension,
    CoreModelMapExtension,
    CableRouteStatusExtension,
    CableSlackLoopExtension,
    StructureSlackLoopExtension,
    CableRouteMapExtension,
]
