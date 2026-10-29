from django.db import migrations


class Migration(migrations.Migration):
    """Free the name `path` on Pathway for the ltree hierarchy column."""

    dependencies = [
        ("netbox_pathways", "0026_backfill_pathway_anchors"),
    ]

    operations = [
        migrations.RenameField(
            model_name="pathway",
            old_name="path",
            new_name="geometry",
        ),
    ]
