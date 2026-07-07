import django.contrib.gis.db.models.fields
from django.db import migrations

from netbox_pathways.geo import get_srid

_SRID = get_srid()


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0018_aerialspan_attachment_height_per_side"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pathway",
            name="path",
            field=django.contrib.gis.db.models.fields.LineStringField(blank=True, null=True, srid=_SRID),
        ),
    ]
