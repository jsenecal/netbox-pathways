"""Convert ConduitBank from standalone model to Pathway subclass.

Drops the old ConduitBank table (verified empty) and recreates it with
multi-table inheritance from Pathway, plus new fields: start_face, end_face.
Also adds start_face/end_face to Conduit and conduit_bank pathway_type choice.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_pathways', '0007_cable_routing_redesign'),
    ]

    operations = [
        # 1. Remove constraint, FK, and field from Conduit that reference old ConduitBank
        migrations.RemoveConstraint(
            model_name='conduit',
            name='unique_position_per_bank',
        ),
        migrations.RemoveField(
            model_name='conduit',
            name='conduit_bank',
        ),
        migrations.RemoveField(
            model_name='conduit',
            name='bank_position',
        ),

        # 2. Drop old standalone ConduitBank
        migrations.DeleteModel(
            name='ConduitBank',
        ),

        # 3. Recreate ConduitBank as Pathway subclass
        migrations.CreateModel(
            name='ConduitBank',
            fields=[
                ('pathway_ptr', models.OneToOneField(
                    auto_created=True, on_delete=django.db.models.deletion.CASCADE,
                    parent_link=True, primary_key=True, serialize=False,
                    to='netbox_pathways.pathway',
                )),
                ('start_face', models.CharField(blank=True, max_length=50,
                    help_text='Which face/wall of the start structure')),
                ('end_face', models.CharField(blank=True, max_length=50,
                    help_text='Which face/wall of the end structure')),
                ('configuration', models.CharField(blank=True, max_length=50,
                    help_text='Layout configuration (e.g., 2x2, 3x3) \u2014 leave blank if irregular')),
                ('total_conduits', models.PositiveIntegerField(blank=True, null=True,
                    help_text='Designed conduit capacity of the bank (leave blank if unknown)')),
                ('encasement_type', models.CharField(blank=True, max_length=50)),
            ],
            options={
                'verbose_name': 'Conduit Bank',
                'verbose_name_plural': 'Conduit Banks',
            },
            bases=('netbox_pathways.pathway',),
        ),

        # 4. Re-add Conduit fields referencing new ConduitBank
        migrations.AddField(
            model_name='conduit',
            name='conduit_bank',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='conduits',
                to='netbox_pathways.conduitbank',
            ),
        ),
        migrations.AddField(
            model_name='conduit',
            name='bank_position',
            field=models.CharField(blank=True, default='', max_length=10,
                help_text='Position in bank (e.g., A1, B2)'),
            preserve_default=False,
        ),

        # 5. Add face fields to Conduit
        migrations.AddField(
            model_name='conduit',
            name='start_face',
            field=models.CharField(blank=True, default='', max_length=50,
                help_text='Which face/wall of the start structure (for standalone conduits)'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='conduit',
            name='end_face',
            field=models.CharField(blank=True, default='', max_length=50,
                help_text='Which face/wall of the end structure (for standalone conduits)'),
            preserve_default=False,
        ),

        # 6. Re-add constraint (after fields exist in state)
        migrations.AddConstraint(
            model_name='conduit',
            constraint=models.UniqueConstraint(
                condition=models.Q(('conduit_bank__isnull', False), ('bank_position__gt', '')),
                fields=['conduit_bank', 'bank_position'],
                name='unique_position_per_bank',
            ),
        ),
    ]
