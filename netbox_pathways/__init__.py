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
        'map_max_native_zoom': 19,
        'map_attribution': '&copy; OpenStreetMap contributors',
        'map_overlays': [],
    }
    django_apps = [
        'django.contrib.gis',
        'leaflet',
        'rest_framework_gis',
    ]

    def ready(self):
        import leaflet as leaflet_mod
        from django.conf import settings

        plugin_cfg = settings.PLUGINS_CONFIG.get('netbox_pathways', {})

        center = (
            plugin_cfg.get('map_center_lat', 45.5017),
            plugin_cfg.get('map_center_lon', -73.5673),
        )
        zoom = plugin_cfg.get('map_zoom', 10)

        # django-leaflet expects TILES as list of (label, url, attrs) tuples.
        # Prefer map_base_layers (same config the main map views use) so form
        # widgets render identical tiles; fall back to map_tiles / OSM default.
        map_max_zoom = 22
        base_layers = plugin_cfg.get('map_base_layers')
        if base_layers:
            tiles = []
            for layer in base_layers:
                attrs = {k: v for k, v in layer.items() if k not in ('name', 'url')}
                # Leaflet's L.tileLayer defaults maxZoom to 18; when multiple
                # layers exist django-leaflet doesn't propagate the map's
                # maxZoom, so tiles go blank beyond z18. Set it explicitly.
                attrs.setdefault('maxZoom', map_max_zoom)
                tiles.append((layer['name'], layer['url'], attrs))
        else:
            tiles_url = plugin_cfg.get('map_tiles',
                'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png')
            max_native_zoom = plugin_cfg.get('map_max_native_zoom', 19)
            attribution = plugin_cfg.get('map_attribution',
                '&copy; OpenStreetMap contributors')
            tiles = [
                ('Street', tiles_url, {
                    'maxZoom': map_max_zoom,
                    'maxNativeZoom': max_native_zoom,
                    'attribution': attribution,
                }),
                ('Satellite',
                 'https://server.arcgisonline.com/ArcGIS/rest/services/'
                 'World_Imagery/MapServer/tile/{z}/{y}/{x}',
                 {
                     'maxZoom': map_max_zoom,
                     'maxNativeZoom': 19,
                     'attribution': 'Esri World Imagery',
                 }),
            ]

        # Set on Django settings for anything that reads it later
        leaflet_config = getattr(settings, 'LEAFLET_CONFIG', {})
        leaflet_config.setdefault('DEFAULT_CENTER', center)
        leaflet_config.setdefault('DEFAULT_ZOOM', zoom)
        leaflet_config.setdefault('TILES', tiles)
        leaflet_config.setdefault('SRID', 4326)
        leaflet_config.setdefault('MAX_ZOOM', map_max_zoom)
        leaflet_config.setdefault('MIN_ZOOM', 1)
        settings.LEAFLET_CONFIG = leaflet_config

        # Patch leaflet's cached app_settings directly (populated at import
        # time before ready() runs, so settings.LEAFLET_CONFIG was missed).
        leaflet_mod.app_settings['DEFAULT_CENTER'] = center
        leaflet_mod.app_settings['DEFAULT_ZOOM'] = zoom
        leaflet_mod.app_settings['TILES'] = tiles
        leaflet_mod.app_settings['SRID'] = 4326
        leaflet_mod.app_settings['MAX_ZOOM'] = map_max_zoom
        leaflet_mod.app_settings['MIN_ZOOM'] = 1
        leaflet_mod.app_settings['RESET_VIEW'] = False

        super().ready()


config = NetBoxPathwaysConfig
