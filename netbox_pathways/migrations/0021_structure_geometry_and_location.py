import django.db.models.deletion
from django.db import migrations, models


def blank_splice_closure_structures(apps, schema_editor):
    """Forward: clear structure_type on rows typed splice_closure.

    A splice closure is Device-shaped (ports, modules) and lives *in* a
    structure, so the type is gone. The field is blank=True, so "" is a valid
    state; operators reclassify to the real container type (handhole, pedestal,
    cabinet, ...) as they encounter them.
    """
    Structure = apps.get_model("netbox_pathways", "Structure")
    Structure.objects.filter(structure_type="splice_closure").update(structure_type="")


def noop(apps, schema_editor):
    """Reverse: blanked rows are indistinguishable from rows that were always
    blank, so there is nothing to restore."""


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0226_add_mptt_tree_indexes"),
        ("netbox_pathways", "0020_pathway_status"),
    ]

    operations = [
        migrations.RunPython(blank_splice_closure_structures, noop),
        migrations.RenameField(
            model_name="structure",
            old_name="location",
            new_name="geometry",
        ),
        migrations.AddField(
            model_name="structure",
            name="location",
            field=models.ForeignKey(
                blank=True,
                help_text="Location within the site where this structure sits",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pathways_structures",
                to="dcim.location",
            ),
        ),
    ]
