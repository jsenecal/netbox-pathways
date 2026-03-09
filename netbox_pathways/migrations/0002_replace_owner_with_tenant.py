import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_pathways', '0001_initial'),
        ('tenancy', '0023_add_mptt_tree_indexes'),
    ]

    operations = [
        # Remove owner from Structure
        migrations.RemoveField(
            model_name='structure',
            name='owner',
        ),
        # Add tenant FK to Structure
        migrations.AddField(
            model_name='structure',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pathways_structures',
                to='tenancy.tenant',
            ),
        ),
        # Add tenant FK to Pathway
        migrations.AddField(
            model_name='pathway',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pathways_pathways',
                to='tenancy.tenant',
            ),
        ),
        # Add tenant FK to ConduitBank
        migrations.AddField(
            model_name='conduitbank',
            name='tenant',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pathways_conduit_banks',
                to='tenancy.tenant',
            ),
        ),
    ]
