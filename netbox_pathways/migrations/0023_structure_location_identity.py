import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Count


def fail_on_shared_locations(apps, schema_editor):
    """Forward guard: the one-to-one constraint below cannot be applied while
    two structures point at the same location, and the raw IntegrityError
    would not say which rows are at fault."""
    Structure = apps.get_model("netbox_pathways", "Structure")
    dupes = (
        Structure.objects.exclude(location__isnull=True)
        .values("location_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
        .order_by("location_id")
    )
    if dupes:
        details = "; ".join(f"location {d['location_id']} is shared by {d['n']} structures" for d in dupes)
        raise RuntimeError(
            "Cannot convert Structure.location to a one-to-one identity link "
            f"while locations are shared: {details}. Reassign or clear the "
            "duplicate structures' location, then re-run the migration."
        )


def noop(apps, schema_editor):
    """Reverse: relaxing the one-to-one back to a plain FK needs no data changes."""


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0022_innerduct_color_hex"),
    ]

    operations = [
        migrations.RunPython(fail_on_shared_locations, noop),
        migrations.AlterField(
            model_name="structure",
            name="location",
            field=models.OneToOneField(
                blank=True,
                help_text="dcim.Location that this structure physically is (e.g. a handhole modelled as a Location)",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pathways_structure",
                to="dcim.location",
            ),
        ),
    ]
