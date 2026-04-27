"""
Geometry helpers: SRID configuration and coordinate transforms for Leaflet display.

WARNING: The SRID is immutable after first migration. Changing it after data has
been loaded will corrupt all spatial data. See README.md for details.
"""

from django.conf import settings

# Leaflet / GeoJSON always use WGS84
LEAFLET_SRID = 4326


def get_srid():
    """
    Return the configured SRID for all geometry storage.

    Raises ImproperlyConfigured if not set in PLUGINS_CONFIG.
    """
    from django.core.exceptions import ImproperlyConfigured

    srid = settings.PLUGINS_CONFIG.get("netbox_pathways", {}).get("srid")
    if srid is None:
        raise ImproperlyConfigured(
            "netbox_pathways: 'srid' is required in PLUGINS_CONFIG['netbox_pathways']. "
            "Example: PLUGINS_CONFIG = {'netbox_pathways': {'srid': 3348}}"
        )
    return int(srid)


def to_leaflet(geom):
    """
    Clone and transform a geometry to EPSG:4326 for Leaflet/GeoJSON display.
    Returns None if geom is None.
    """
    if geom is None:
        return None
    srid = get_srid()
    if srid == LEAFLET_SRID:
        return geom
    clone = geom.clone()
    clone.transform(LEAFLET_SRID)
    return clone


def point_to_lonlat(geom):
    """
    Return (lon, lat) tuple from a point or centroid, transformed to 4326.
    Works with Point, Polygon, or any geometry type.
    Returns None if geom is None.
    """
    if geom is None:
        return None
    pt = to_leaflet(geom)
    if pt.geom_type != "Point":
        pt = pt.centroid
    return (pt.x, pt.y)


def point_to_latlon(geom):
    """
    Return (lat, lon) tuple from a point or centroid, transformed to 4326.
    Returns None if geom is None.
    """
    result = point_to_lonlat(geom)
    if result is None:
        return None
    return (result[1], result[0])


def linestring_to_coords(geom):
    """
    Return list of [lon, lat] coordinate pairs, transformed to 4326.
    Returns empty list if geom is None.
    """
    if geom is None:
        return []
    line = to_leaflet(geom)
    return [[p[0], p[1]] for p in line.coords]
