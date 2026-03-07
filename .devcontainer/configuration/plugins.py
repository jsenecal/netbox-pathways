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
    },
}
