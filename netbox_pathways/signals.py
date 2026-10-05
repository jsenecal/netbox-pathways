from dcim.models import Location
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from .attachment import refresh_anchors, refresh_for_locations, refresh_for_site
from .models import CableSegment, Pathway, SiteGeometry, Structure


@receiver(pre_save, sender=CableSegment)
def enforce_cable_routability(sender, instance, **kwargs):
    """Enforce that cable has A+B terminations before saving segments."""
    if not instance.cable_id:
        return
    from dcim.models import CableTermination

    a_exists = CableTermination.objects.filter(
        cable_id=instance.cable_id,
        cable_end="A",
    ).exists()
    b_exists = CableTermination.objects.filter(
        cable_id=instance.cable_id,
        cable_end="B",
    ).exists()
    if not (a_exists and b_exists):
        raise ValidationError("Cable must have both A and B terminations before routing.")


# Stored pathway anchors (attachment.resolve_anchor) follow the hierarchy.
# Structure.location changes are handled in Structure.save(), which knows the
# old value; the hooks below cover changes made elsewhere.


@receiver(post_save, sender=Location)
def refresh_anchors_on_location_save(sender, instance, **kwargs):
    """A moved location (new parent or site) changes what its subtree attaches to."""
    refresh_for_locations([instance])


@receiver(post_delete, sender=SiteGeometry)
def refresh_anchors_on_site_geometry_delete(sender, instance, **kwargs):
    """Unlinking a site's structure changes what its locations attach to.

    Linking and relinking are handled in SiteGeometry.save(), which knows the
    old structure and skips boundary-only edits.
    """
    refresh_for_site(instance.site_id)


@receiver(pre_delete, sender=Structure)
def remember_anchored_pathways(sender, instance, **kwargs):
    """Pathways anchored to a deleted structure fall back up the walk."""
    instance._anchored_pathway_pks = list(
        Pathway.objects.filter(Q(start_anchor=instance) | Q(end_anchor=instance)).values_list("pk", flat=True)
    )


@receiver(post_delete, sender=Structure)
def refresh_anchors_on_structure_delete(sender, instance, **kwargs):
    pks = getattr(instance, "_anchored_pathway_pks", None)
    if pks:
        refresh_anchors(Pathway.objects.filter(pk__in=pks))
