"""The window.PATHWAYS_CONFIG keys shared by the plugin's Leaflet pages.

The full map, the route planner and the detail-map head each build their
own config on top of these, so the API base and the drawn-type list are
worked out in one place.
"""

from django.conf import settings
from django.urls import reverse

from .pathway_types import DRAWN_TYPES_ORDERED


def base_map_config():
    """Keys every map page reads: the geo API base and the types the map draws."""
    return {
        "apiBase": f"{reverse('plugins-api:netbox_pathways-api:api-root')}geo/",
        "drawnTypes": list(DRAWN_TYPES_ORDERED),
    }


def tile_map_config():
    """Base-map keys from PLUGINS_CONFIG shared by the full map and the detail maps."""
    plugin_cfg = settings.PLUGINS_CONFIG.get("netbox_pathways", {})
    return {
        "maxNativeZoom": plugin_cfg.get("map_max_native_zoom", 19),
        "skipInfoZoom": plugin_cfg.get("map_skip_info_zoom", 17),
        "overlays": plugin_cfg.get("map_overlays", []),
    }
