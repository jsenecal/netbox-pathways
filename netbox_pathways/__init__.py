from netbox.plugins import PluginConfig

__version__ = '0.1.0'


class NetBoxPathwaysConfig(PluginConfig):
    name = 'netbox_pathways'
    verbose_name = 'NetBox Pathways'
    description = 'Physical cable plant infrastructure documentation with GIS capabilities'
    version = __version__
    author = 'Jonathan Senecal'
    author_email = 'contact@jonathansenecal.com'
    base_url = 'pathways'
    required_settings = ['srid']
    default_settings = {
        'map_center_lat': 45.5017,
        'map_center_lon': -73.5673,
        'map_zoom': 10,
        'map_tiles': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    }
    django_apps = [
        'django.contrib.gis',
        'leaflet',
        'rest_framework_gis',
    ]

    def ready(self):
        from django.conf import settings

        plugin_cfg = settings.PLUGINS_CONFIG.get('netbox_pathways', {})
        leaflet_config = getattr(settings, 'LEAFLET_CONFIG', {})

        leaflet_config.setdefault('DEFAULT_CENTER', (
            plugin_cfg.get('map_center_lat', 45.5017),
            plugin_cfg.get('map_center_lon', -73.5673),
        ))
        leaflet_config.setdefault('DEFAULT_ZOOM', plugin_cfg.get('map_zoom', 10))
        leaflet_config.setdefault('TILES', plugin_cfg.get('map_tiles',
            'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png'))
        leaflet_config.setdefault('SRID', 4326)

        settings.LEAFLET_CONFIG = leaflet_config

        super().ready()


config = NetBoxPathwaysConfig
