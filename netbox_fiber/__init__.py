from netbox.plugins import PluginConfig

__version__ = '0.1.0'


class NetBoxFiberConfig(PluginConfig):
    name = 'netbox_fiber'
    verbose_name = 'NetBox Fiber'
    description = 'Fiber optic network documentation with GIS capabilities'
    version = __version__
    author = 'NetBox Fiber Team'
    author_email = 'admin@example.com'
    base_url = 'fiber'
    required_settings = []
    default_settings = {
        'map_center_lat': 39.8283,
        'map_center_lon': -98.5795,
        'map_zoom': 5,
        'enable_3d_view': False,
    }


config = NetBoxFiberConfig