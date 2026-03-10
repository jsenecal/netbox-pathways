"""
Plugin related config
"""

PLUGINS = [
    # "netbox_initializers",  # Loads demo data
    "netbox_pathways",
]

PLUGINS_CONFIG = {
    # "netbox_initializers": {},
    "netbox_pathways": {
        "srid": 3348,  # NAD83(CSRS) — required, no default
        "map_base_layers": [
            {
                "name": "Dark",
                "url": "https://api.mapbox.com/styles/v1/mapbox/light-v11/tiles/{z}/{x}/{y}?access_token=MAPBOX_TOKEN_REMOVED",
                "tileSize": 512,
                "zoomOffset": -1,
                "attribution": "&copy; <a href='https://www.mapbox.com/'>Mapbox</a> &copy; <a href='https://www.openstreetmap.org/copyright'>OSM</a>",
                "maxNativeZoom": 22,
            },
            {
                "name": "Light",
                "url": "https://api.mapbox.com/styles/v1/mapbox/dark-v11/tiles/{z}/{x}/{y}?access_token=MAPBOX_TOKEN_REMOVED",
                "tileSize": 512,
                "zoomOffset": -1,
                "attribution": "&copy; <a href='https://www.mapbox.com/'>Mapbox</a> &copy; <a href='https://www.openstreetmap.org/copyright'>OSM</a>",
                "maxNativeZoom": 22,
            },
            {
                "name": "Satellite",
                "url": "https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{z}/{x}/{y}?access_token=MAPBOX_TOKEN_REMOVED",
                "tileSize": 512,
                "zoomOffset": -1,
                "attribution": "&copy; <a href='https://www.mapbox.com/'>Mapbox</a>",
                "maxNativeZoom": 22,
            },
        ],
    },
}
