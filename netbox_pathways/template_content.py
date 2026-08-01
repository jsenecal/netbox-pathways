from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse
from netbox.plugins.templates import PluginTemplateExtension

from . import models
from .geo import linestring_to_coords, point_to_latlon, to_leaflet


def _leaflet_head():
    """Return HTML to load Leaflet and geoman assets in <head>."""
    css = [
        static("netbox_pathways/vendor/leaflet/leaflet.css"),
        static("netbox_pathways/vendor/geoman/leaflet-geoman.css"),
        static("netbox_pathways/vendor/MarkerCluster.css"),
        static("netbox_pathways/vendor/MarkerCluster.Default.css"),
        static("netbox_pathways/css/leaflet-theme.css"),
    ]
    js = [
        static("netbox_pathways/vendor/leaflet/leaflet.js"),
        static("netbox_pathways/vendor/geoman/leaflet-geoman.js"),
        static("netbox_pathways/vendor/leaflet.markercluster.js"),
        static("netbox_pathways/dist/pathways-field.min.js"),
        static("netbox_pathways/dist/endpoint-markers.min.js"),
        static("netbox_pathways/dist/reference-layer.min.js"),
    ]
    html = ""
    for href in css:
        html += f'<link rel="stylesheet" href="{href}" />\n'
    for src in js:
        html += f'<script src="{src}"></script>\n'
    return html


PATHWAY_COLORS = {
    "conduit": "brown",
    "aerial": "blue",
    "direct_buried": "gray",
    "innerduct": "orange",
    "microduct": "purple",
    "tray": "green",
    "raceway": "cyan",
    "submarine": "navy",
}

STRUCTURE_COLORS = {
    "pole": "green",
    "manhole": "blue",
    "handhole": "cyan",
    "cabinet": "orange",
    "vault": "purple",
    "pedestal": "yellow",
    "building_entrance": "red",
    "tower": "darkred",
    "roof": "gray",
    "equipment_room": "teal",
    "telecom_closet": "indigo",
    "riser_room": "pink",
}


def _pathway_line(pathway):
    """Build a line dict from a Pathway instance."""
    if not pathway.path:
        return None
    return {
        "coords": linestring_to_coords(pathway.path),
        "name": str(pathway),
        "color": PATHWAY_COLORS.get(pathway.pathway_type, "gray"),
        "url": pathway.get_absolute_url(),
    }


def _structure_point(structure, color=None, muted=False):
    """Build a point dict from a Structure instance.

    `muted` marks a structure shown only as context for something else (the far
    end of a pathway leaving the page's subject); the map draws those faded.
    The key is omitted when false so the common case costs nothing in a payload
    that can carry 500 points.
    """
    latlon = point_to_latlon(structure.centroid)
    if latlon is None:
        return None
    point = {
        "lat": latlon[0],
        "lon": latlon[1],
        "name": structure.name,
        "structure_type": structure.get_structure_type_display(),
        "color": color or STRUCTURE_COLORS.get(structure.structure_type, "gray"),
        "url": structure.get_absolute_url(),
    }
    if muted:
        point["muted"] = True
    return point


def _footprint_ring(structure):
    """Return the exterior ring of a Structure's footprint, or None.

    A Structure is drawn as either a marker or a footprint -- the geometry
    widget offers drawMarker and drawPolygon only -- so anything that is not a
    polygon is a point as far as the map is concerned.
    """
    geom = structure.geometry
    if geom is None or geom.geom_type != "Polygon":
        return None
    return [[p[0], p[1]] for p in to_leaflet(geom).exterior_ring.coords]


def _add_structure(data, structure, color=None, muted=False):
    """Append a Structure to `data` as a footprint outline or a point marker.

    Footprints keep their centroid alongside the ring so the client can swap in
    a single icon below the footprint zoom, where an outline is sub-pixel.
    """
    shape = _structure_point(structure, color=color, muted=muted)
    if shape is None:
        return
    ring = _footprint_ring(structure)
    if ring is None:
        data["points"].append(shape)
    else:
        shape["coords"] = ring
        data["polygons"].append(shape)


class LeafletHeadExtension(PluginTemplateExtension):
    """Load Leaflet + detail-map assets globally via {% plugin_head %}.

    NetBox's base template calls {% plugin_head %} without an object, so only
    extensions with models=None (global) are invoked.  Setting a models list
    here would silently prevent head() from ever being called.
    """

    def head(self):
        import json

        from django.conf import settings

        from . import NetBoxPathwaysConfig

        plugin_cfg = settings.PLUGINS_CONFIG.get("netbox_pathways", {})

        api_base = reverse("plugins-api:netbox_pathways-api:api-root")
        config = {
            **NetBoxPathwaysConfig._map_config,
            "maxNativeZoom": plugin_cfg.get("map_max_native_zoom", 19),
            "skipInfoZoom": plugin_cfg.get("map_skip_info_zoom", 17),
            "apiBase": f"{api_base}geo/",
            "overlays": plugin_cfg.get("map_overlays", []),
        }

        detail_js = static("netbox_pathways/dist/detail-map.min.js")
        config_js = f"<script>window.PATHWAYS_CONFIG={json.dumps(config)};</script>\n"
        return _leaflet_head() + config_js + f'<script src="{detail_js}"></script>\n'


class PluginModelMapExtension(PluginTemplateExtension):
    """Map panel on plugin model detail pages (Structure, Pathway subtypes, etc.)."""

    models = [
        "netbox_pathways.structure",
        "netbox_pathways.pathway",
        "netbox_pathways.conduit",
        "netbox_pathways.aerialspan",
        "netbox_pathways.directburied",
        "netbox_pathways.innerduct",
        "netbox_pathways.conduitbank",
        "netbox_pathways.conduitjunction",
    ]

    def right_page(self):
        obj = self.context["object"]
        geo_data = self._get_geo_data(obj)
        if not geo_data:
            return ""
        map_id = f"geo-{obj._meta.model_name}-{obj.pk}"
        return self.render(
            "netbox_pathways/inc/geo_map_panel.html",
            extra_context={
                "geo_data": geo_data,
                "map_id": map_id,
                "data_id": f"{map_id}-data",
                "panel_title": "Location",
            },
        )

    def _get_geo_data(self, obj):
        data = {"points": [], "lines": [], "polygons": []}

        if isinstance(obj, models.Structure):
            _add_structure(data, obj)

        elif isinstance(obj, models.ConduitBank):
            line = _pathway_line(obj)
            if line:
                data["lines"].append(line)
            for struct in (obj.start_structure, obj.end_structure):
                if struct:
                    _add_structure(data, struct, color="orange")

        elif isinstance(obj, models.ConduitJunction):
            # Show the trunk conduit line for context
            if obj.trunk_conduit_id:
                line = _pathway_line(obj.trunk_conduit)
                if line:
                    data["lines"].append(line)
            # Show the computed junction point
            loc = obj.location
            if loc:
                data["points"].append(
                    {
                        "lat": loc.y,
                        "lon": loc.x,
                        "name": str(obj),
                        "color": "red",
                    }
                )

        elif isinstance(obj, models.Pathway):
            # Pathway base or any MTI subtype (Conduit, AerialSpan, etc.)
            line = _pathway_line(obj)
            if line:
                data["lines"].append(line)
            # Start/end structure markers
            if obj.start_structure_id:
                _add_structure(data, obj.start_structure, color="green")
            if obj.end_structure_id:
                _add_structure(data, obj.end_structure, color="red")

        if not data["points"] and not data["lines"] and not data["polygons"]:
            return None
        return data


class CoreModelMapExtension(PluginTemplateExtension):
    """Infrastructure overview map on Site and Location detail pages."""

    models = ["dcim.site", "dcim.location"]

    def right_page(self):
        obj = self.context["object"]
        geo_data = self._get_geo_data(obj)
        if not geo_data:
            return ""
        map_id = f"geo-{obj._meta.model_name}-{obj.pk}"
        return self.render(
            "netbox_pathways/inc/geo_map_panel.html",
            extra_context={
                "geo_data": geo_data,
                "map_id": map_id,
                "data_id": f"{map_id}-data",
                "panel_title": "Pathways Infrastructure",
                "dynamic_layers": "true",
            },
        )

    def _get_geo_data(self, obj):
        from dcim.models import Location, Site

        data = {"points": [], "lines": [], "polygons": []}

        if isinstance(obj, Site):
            # Show site boundary if present
            try:
                site_geo = models.SiteGeometry.objects.select_related("structure").get(site=obj)
                geom = site_geo.effective_geometry
                if geom:
                    from .geo import to_leaflet

                    geom = to_leaflet(geom)
                    if geom and geom.geom_type in ("Polygon", "MultiPolygon"):
                        if geom.geom_type == "Polygon":
                            coords = [[p[0], p[1]] for p in geom.exterior_ring.coords]
                        else:
                            coords = [[p[0], p[1]] for p in geom[0].exterior_ring.coords]
                        data["lines"].append(
                            {
                                "coords": coords,
                                "name": f"Site boundary: {obj.name}",
                                "color": "#333",
                            }
                        )
            except models.SiteGeometry.DoesNotExist:
                pass

            for s in models.Structure.objects.filter(site=obj).only(
                "name",
                "structure_type",
                "geometry",
            )[:500]:
                _add_structure(data, s)

            pathways = models.Pathway.objects.filter(
                Q(start_structure__site=obj) | Q(end_structure__site=obj),
            ).only(
                "label",
                "pathway_type",
                "path",
            )[:500]
            for p in pathways:
                line = _pathway_line(p)
                if line:
                    data["lines"].append(line)

        elif isinstance(obj, Location):
            # Locations nest, and core's LocationView counts related objects
            # across the whole subtree -- so roll up here too, or the map
            # contradicts the Related Objects card on the same page.
            locations = obj.get_descendants(include_self=True)

            # Structures sitting in those locations, keyed by pk so that a
            # structure reached from more than one direction below (several
            # pathways sharing an endpoint, or an endpoint that is itself in
            # this subtree) yields a single marker rather than stacked ones.
            structures = {
                s.pk: s
                for s in models.Structure.objects.filter(location__in=locations).only(
                    "name",
                    "structure_type",
                    "geometry",
                )[:500]
            }
            in_location = set(structures)

            pathways = (
                models.Pathway.objects.filter(
                    Q(start_location__in=locations) | Q(end_location__in=locations),
                )
                .select_related(
                    "start_structure",
                    "end_structure",
                )
                .only(
                    "label",
                    "pathway_type",
                    "path",
                    "start_structure_id",
                    "end_structure_id",
                    "start_structure__name",
                    "start_structure__structure_type",
                    "start_structure__geometry",
                    "end_structure__name",
                    "end_structure__structure_type",
                    "end_structure__geometry",
                )[:500]
            )
            for p in pathways:
                line = _pathway_line(p)
                if line:
                    data["lines"].append(line)
                # Endpoint structures give the far end of pathways leaving here
                for endpoint in (p.start_structure, p.end_structure):
                    if endpoint:
                        structures.setdefault(endpoint.pk, endpoint)

            for pk, s in structures.items():
                _add_structure(data, s, muted=pk not in in_location)

        if not data["points"] and not data["lines"] and not data["polygons"]:
            return None
        return data


template_extensions = [
    LeafletHeadExtension,
    PluginModelMapExtension,
    CoreModelMapExtension,
]
