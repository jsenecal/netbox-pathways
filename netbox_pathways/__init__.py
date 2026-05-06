import logging

from netbox.plugins import PluginConfig

__version__ = "0.1.0"

logger = logging.getLogger(__name__)


class NetBoxPathwaysConfig(PluginConfig):
    name = "netbox_pathways"
    verbose_name = "NetBox Pathways"
    description = "Physical cable plant infrastructure documentation with GIS capabilities"
    version = __version__
    author = "Jonathan Senecal"
    author_email = "contact@jonathansenecal.com"
    base_url = "pathways"
    graphql_schema = "graphql.schema.schema"
    required_settings = ["srid"]
    default_settings = {
        "map_center_lat": 45.5017,
        "map_center_lon": -73.5673,
        "map_zoom": 10,
        "map_tiles": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "map_max_native_zoom": 19,
        "map_attribution": "&copy; OpenStreetMap contributors",
        "map_overlays": [],
    }
    django_apps = [
        "django.contrib.gis",
        "rest_framework_gis",
    ]

    # Populated in ready(), consumed by template_content.py
    _map_config = {}

    def ready(self):
        from django.conf import settings

        plugin_cfg = settings.PLUGINS_CONFIG.get("netbox_pathways", {})
        max_zoom = 22

        base_layers = plugin_cfg.get("map_base_layers")
        if base_layers:
            tiles = []
            for layer in base_layers:
                tile = dict(layer.items())
                tile.setdefault("maxZoom", max_zoom)
                tiles.append(tile)
        else:
            tiles_url = plugin_cfg.get(
                "map_tiles",
                "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            )
            max_native = plugin_cfg.get("map_max_native_zoom", 19)
            attribution = plugin_cfg.get(
                "map_attribution",
                "&copy; OpenStreetMap contributors",
            )
            tiles = [
                {
                    "name": "Street",
                    "url": tiles_url,
                    "maxZoom": max_zoom,
                    "maxNativeZoom": max_native,
                    "attribution": attribution,
                },
                {
                    "name": "Satellite",
                    "url": (
                        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                    ),
                    "maxZoom": max_zoom,
                    "maxNativeZoom": 19,
                    "attribution": "Esri World Imagery",
                },
            ]

        NetBoxPathwaysConfig._map_config = {
            "baseLayers": tiles,
            "center": [
                plugin_cfg.get("map_center_lat", 45.5017),
                plugin_cfg.get("map_center_lon", -73.5673),
            ],
            "zoom": plugin_cfg.get("map_zoom", 10),
            "minZoom": 1,
            "maxZoom": max_zoom,
        }

        super().ready()

        # Register signals
        from . import signals  # noqa: F401

        logger.info("%s plugin loaded", self.name)


config = NetBoxPathwaysConfig
