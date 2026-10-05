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


def refresh_anchors(pathways):
    """Recompute stored anchors for `pathways`; write only rows that changed.

    Anchors are derived data, so rows are updated in place without save()
    or a change-log entry. Returns the number of rows updated.
    """
    from .models import Pathway

    updated = 0
    memo = {}
    rows = pathways.select_related("start_structure", "end_structure", "start_location", "end_location")
    for pathway in rows:
        anchors = pathway.resolved_anchor_ids(memo)
        if anchors != (pathway.start_anchor_id, pathway.end_anchor_id):
            Pathway.objects.filter(pk=pathway.pk).update(start_anchor_id=anchors[0], end_anchor_id=anchors[1])
            updated += 1
    return updated


def _refresh_matching(query):
    """Refresh anchors of pathways matching `query`, if there are any.

    Selecting pks first keeps the anchor columns out of the query when nothing
    matches, which is what lets hierarchy saves run during migration tests
    against a pre-anchor schema.
    """
    from .models import Pathway

    pks = list(Pathway.objects.filter(query).values_list("pk", flat=True))
    if pks:
        refresh_anchors(Pathway.objects.filter(pk__in=pks))


def refresh_for_locations(locations):
    """Refresh anchors of pathways naming any of `locations` or their descendants.

    Each location is re-read from the database: NetBox maintains the tree
    columns in the database and may update them after post_save fires, so the
    in-memory instance can still describe the old position.
    """
    from dcim.models import Location
    from django.db.models import Q

    pks = set()
    for location in locations:
        if location is None:
            continue
        fresh = Location.objects.filter(pk=location.pk).first()
        if fresh is not None:
            pks.update(fresh.get_descendants(include_self=True).values_list("pk", flat=True))
    if pks:
        _refresh_matching(Q(start_location_id__in=pks) | Q(end_location_id__in=pks))


def refresh_for_site(site_id):
    """Refresh anchors of pathways naming any location in the site."""
    from django.db.models import Q

    _refresh_matching(Q(start_location__site_id=site_id) | Q(end_location__site_id=site_id))
