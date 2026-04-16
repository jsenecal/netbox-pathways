from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_pathways', '0010_structure_status'),
    ]

    operations = [
        # Rename the field first (preserves data)
        migrations.RenameField(
            model_name='pathway',
            old_name='name',
            new_name='label',
        ),
        migrations.RenameField(
            model_name='conduitjunction',
            old_name='name',
            new_name='label',
        ),
        # Then alter to drop unique=True and allow blank
        migrations.AlterField(
            model_name='pathway',
            name='label',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AlterField(
            model_name='conduitjunction',
            name='label',
            field=models.CharField(blank=True, max_length=100),
        ),
        # Update ordering
        migrations.AlterModelOptions(
            name='pathway',
            options={'ordering': ['pk']},
        ),
        migrations.AlterModelOptions(
            name='conduitjunction',
            options={'ordering': ['pk']},
        ),
    ]
