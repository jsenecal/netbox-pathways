"""Resolve where a cable's ends sit in the pathway network.

A cable terminates on DCIM objects -- interfaces, ports, circuit terminations --
not on pathways infrastructure. To offer the pathways a cable could plausibly
enter, a cable end is translated into graph nodes: the terminating device's
location and its ancestors, structures sitting at those locations, the structure
that represents the site, and the remaining structures in the site.

The set is flat: a cable end can plausibly be several nodes and we do not guess
between them, because guessing one silently offered the wrong pathways. It is
ordered by precision, most precise first, which is what the endpoint readout
displays and what the route planner walks when it needs a single unambiguous
structure.
"""

from dataclasses import dataclass

from dcim.models import CableTermination, Location, Site

from . import models

# Message and remedy per unresolved reason, kept here rather than in a template
# so the wording is testable. `message` is formatted with `end` and `place`.
REASON_MESSAGES = {
    "termination_not_sited": (
        "The {end} termination is not associated with a site or location.",
        "Terminate the circuit at a site, or route this cable from the other end.",
    ),
    "nothing_in_plant": (
        "Nothing at {place} is modeled in Pathways.",
        "Link the site to a structure in Site Geometry, or set a site or location on your structures.",
    ),
}


@dataclass(frozen=True)
class AnchorSet:
    """Graph nodes one end of a cable could plausibly sit at.

    `nodes` and `labels` are parallel: `labels[i]` names `nodes[i]`.
    `unresolved_reason` is set exactly when `nodes` is empty.
    """

    nodes: tuple[tuple[str, int], ...] = ()
    labels: tuple[str, ...] = ()
    site: Site | None = None
    location: Location | None = None
    unresolved_reason: str | None = None

    @property
    def structures(self) -> tuple[int, ...]:
        """Candidate structure pks, most precise first."""
        return tuple(pk for kind, pk in self.nodes if kind == "structure")

    @property
    def is_resolved(self) -> bool:
        return bool(self.nodes)


def cable_end_nodes(cable, cable_end):
    """Return the AnchorSet for one end of a cable. `cable_end` is "A" or "B"."""
    termination = (
        CableTermination.objects.filter(cable=cable, cable_end=cable_end).select_related("_site", "_location").first()
    )
    if termination is None or (termination._site_id is None and termination._location_id is None):
        return AnchorSet(unresolved_reason="termination_not_sited")

    locations = _location_chain(termination._location)
    nodes = [("location", location.pk) for location in locations]
    labels = [str(location) for location in locations]

    seen = set()
    for structure in _candidate_structures(termination._site_id, [location.pk for location in locations]):
        if structure.pk in seen:
            continue
        seen.add(structure.pk)
        nodes.append(("structure", structure.pk))
        labels.append(str(structure))

    if not nodes:
        return AnchorSet(
            site=termination._site,
            location=termination._location,
            unresolved_reason="nothing_in_plant",
        )
    return AnchorSet(
        nodes=tuple(nodes),
        labels=tuple(labels),
        site=termination._site,
        location=termination._location,
    )


def describe(anchor, end_label):
    """Display data for one cable end: its labels, or a message and a remedy."""
    if anchor.is_resolved:
        return {"end": end_label, "labels": list(anchor.labels), "message": None, "remedy": None}
    message, remedy = REASON_MESSAGES[anchor.unresolved_reason]
    place = anchor.location or anchor.site
    return {
        "end": end_label,
        "labels": [],
        "message": message.format(end=end_label, place=place),
        "remedy": remedy,
    }


def _location_chain(location):
    """The location and its ancestors, deepest first. Empty when unset."""
    if location is None:
        return []
    return [location, *location.get_ancestors(ascending=True)]


def _candidate_structures(site_id, location_pks):
    """Structures for a cable end, most precise first.

    Structures sitting at the termination's locations outrank the site's
    representative structure, which outranks the rest of the site's structures.
    Duplicates are expected and are removed by the caller.
    """
    ordered = []
    if location_pks:
        ordered.extend(models.Structure.objects.filter(location_id__in=location_pks))
    if site_id:
        geometry = (
            models.SiteGeometry.objects.filter(site_id=site_id, structure__isnull=False)
            .select_related("structure")
            .first()
        )
        if geometry:
            ordered.append(geometry.structure)
        ordered.extend(models.Structure.objects.filter(site_id=site_id))
    return ordered
