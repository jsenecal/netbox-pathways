import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0226_add_mptt_tree_indexes"),
        ("netbox_pathways", "0023_structure_location_identity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pathway",
            name="start_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pathways_out",
                to="dcim.location",
            ),
        ),
        migrations.AlterField(
            model_name="pathway",
            name="end_location",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pathways_in",
                to="dcim.location",
            ),
        ),
    ]
