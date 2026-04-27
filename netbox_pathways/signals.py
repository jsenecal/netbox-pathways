from django.core.exceptions import ValidationError
from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import CableSegment


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
