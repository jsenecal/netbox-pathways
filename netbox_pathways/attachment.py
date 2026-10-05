"""Which structure a pathway end is attached to.

A pathway end names a structure, a dcim.Location, or (conduits) a junction.
A structure can *be* a location (Structure.location) and can *be* a site
(SiteGeometry.structure); every location sits in a site and may sit in parent
locations. An end naming a location attaches to the nearest enclosing
structure:

1. the location's own structure,
2. else the nearest ancestor location's structure,
3. else the structure representing the location's site.

Structure.site ("the structure sits in this site") never attaches anything.
This is the one rule; docs/user-guide/attachment.md explains it to users.
"""

from .registry import LOCATION_IDENTITY_ACCESSOR


def location_chain(location):
    """The location and its ancestors, nearest first. Empty when unset."""
    if location is None:
        return []
    return [location, *location.get_ancestors(ascending=True)]


def resolve_anchor(structure, location):
    """The structure an end naming `structure` and/or `location` attaches to, or None."""
    from .models import SiteGeometry

    if structure is not None:
        return structure
    if location is None:
        return None
    for candidate in location_chain(location):
        # The reverse one-to-one raises an AttributeError-compatible
        # DoesNotExist when the location has no structure of its own.
        identity = getattr(candidate, LOCATION_IDENTITY_ACCESSOR, None)
        if identity is not None:
            return identity
    site_geometry = (
        SiteGeometry.objects.filter(site_id=location.site_id, structure__isnull=False)
        .select_related("structure")
        .first()
    )
    return site_geometry.structure if site_geometry else None
