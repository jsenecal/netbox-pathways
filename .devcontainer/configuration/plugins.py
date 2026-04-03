"""
Plugin related config
"""
import os

PLUGINS = [
    # "netbox_initializers",  # Loads demo data
    "netbox_pathways",
]

_MAPBOX_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN", "")

_PATHWAYS_CONFIG = {
    "srid": 3348,  # NAD83(CSRS) — required, no default
}

if _MAPBOX_TOKEN:
    _PATHWAYS_CONFIG["map_base_layers"] = [
        {
            "name": "Dark",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/navigation-night-v1/tiles/{{z}}/{{x}}/{{y}}?access_token={_MAPBOX_TOKEN}",
            "tileSize": 512,
            "zoomOffset": -1,
            "attribution": "&copy; <a href='https://www.mapbox.com/'>Mapbox</a> &copy; <a href='https://www.openstreetmap.org/copyright'>OSM</a>",
            "maxNativeZoom": 22,
        },
        {
            "name": "Light",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/navigation-day-v1/tiles/{{z}}/{{x}}/{{y}}?access_token={_MAPBOX_TOKEN}",
            "tileSize": 512,
            "zoomOffset": -1,
            "attribution": "&copy; <a href='https://www.mapbox.com/'>Mapbox</a> &copy; <a href='https://www.openstreetmap.org/copyright'>OSM</a>",
            "maxNativeZoom": 22,
        },
        {
            "name": "Satellite",
            "url": f"https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/{{z}}/{{x}}/{{y}}?access_token={_MAPBOX_TOKEN}",
            "tileSize": 512,
            "zoomOffset": -1,
            "attribution": "&copy; <a href='https://www.mapbox.com/'>Mapbox</a>",
            "maxNativeZoom": 22,
        },
    ]

PLUGINS_CONFIG = {
    # "netbox_initializers": {},
    "netbox_pathways": _PATHWAYS_CONFIG,
}
