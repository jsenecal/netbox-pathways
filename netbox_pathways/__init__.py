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
    required_settings = []
    default_settings = {
        'map_center_lat': 45.5017,
        'map_center_lon': -73.5673,
        'map_zoom': 10,
    }
    django_apps = [
        'django.contrib.gis',
        'rest_framework_gis',
    ]


config = NetBoxPathwaysConfig
