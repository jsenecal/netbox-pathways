from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0019_alter_pathway_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="pathway",
            name="status",
            field=models.CharField(default="active", max_length=50),
        ),
        migrations.AddIndex(
            model_name="pathway",
            index=models.Index(fields=["status"], name="netbox_path_status_09488a_idx"),
        ),
    ]
