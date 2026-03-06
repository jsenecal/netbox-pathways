from django.db.models import Q
from django.templatetags.static import static
from netbox.plugins.templates import PluginTemplateExtension

from . import models

LEAFLET_HEAD = (
    '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />\n'
    '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>\n'
)

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
        'coords': [[p[0], p[1]] for p in pathway.path.coords],
        'name': pathway.name,
        'color': PATHWAY_COLORS.get(pathway.pathway_type, 'gray'),
        'url': pathway.get_absolute_url(),
    }


def _structure_point(structure, color=None):
    """Build a point dict from a Structure instance."""
    if not structure.location:
        return None
    return {
        'lat': structure.location.y,
        'lon': structure.location.x,
        'name': structure.name,
        'color': color or STRUCTURE_COLORS.get(structure.structure_type, 'gray'),
        'url': structure.get_absolute_url(),
    }


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

    def head(self):
        detail_js = static('netbox_pathways/js/detail-map.js')
        return LEAFLET_HEAD + f'<script src="{detail_js}"></script>\n'

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
            if obj.structure_id:
                pt = _structure_point(obj.structure, color='orange')
                if pt:
                    pt['name'] = f'{obj.name} @ {obj.structure.name}'
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
                    'name': obj.name,
                    'color': 'red',
                })

        elif isinstance(obj, models.Pathway):
            # Pathway base or any MTI subtype (Conduit, AerialSpan, etc.)
            line = _pathway_line(obj)
            if line:
                data['lines'].append(line)
            # Start/end structure markers
            if obj.start_structure_id and obj.start_structure.location:
                data['points'].append({
                    'lat': obj.start_structure.location.y,
                    'lon': obj.start_structure.location.x,
                    'name': str(obj.start_structure),
                    'color': 'green',
                })
            if obj.end_structure_id and obj.end_structure.location:
                data['points'].append({
                    'lat': obj.end_structure.location.y,
                    'lon': obj.end_structure.location.x,
                    'name': str(obj.end_structure),
                    'color': 'red',
                })

        if not data['points'] and not data['lines']:
            return None
        return data


class CoreModelMapExtension(PluginTemplateExtension):
    """Infrastructure overview map on Site and Location detail pages."""

    models = ['dcim.site', 'dcim.location']

    def head(self):
        detail_js = static('netbox_pathways/js/detail-map.js')
        return LEAFLET_HEAD + f'<script src="{detail_js}"></script>\n'

    def full_width_page(self):
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
        })

    def _get_geo_data(self, obj):
        from dcim.models import Location, Site

        data = {'points': [], 'lines': []}

        if isinstance(obj, Site):
            for s in models.Structure.objects.filter(site=obj).only(
                'name', 'structure_type', 'location',
            )[:500]:
                pt = _structure_point(s)
                if pt:
                    data['points'].append(pt)

            pathways = models.Pathway.objects.filter(
                Q(start_structure__site=obj) | Q(end_structure__site=obj),
            ).select_related(
                'start_structure', 'end_structure',
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
            )[:500]
            for p in pathways:
                line = _pathway_line(p)
                if line:
                    data['lines'].append(line)
                # Also show endpoint structures
                if p.start_structure_id and p.start_structure.location:
                    data['points'].append(_structure_point(p.start_structure))
                if p.end_structure_id and p.end_structure.location:
                    data['points'].append(_structure_point(p.end_structure))

        if not data['points'] and not data['lines']:
            return None
        return data


template_extensions = [PluginModelMapExtension, CoreModelMapExtension]
