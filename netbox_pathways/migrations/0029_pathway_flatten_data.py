"""Copy the subtype rows onto Pathway and delete retired microduct rows.

The work is done by tested helpers in netbox_pathways.upgrade. Deleting
microducts cannot be reversed; reversing the copy rebuilds the child rows.
"""

from django.db import migrations

from netbox_pathways.upgrade import copy_subtype_rows, delete_microducts, uncopy_subtype_rows


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0028_pathway_flatten_columns"),
    ]

    operations = [
        migrations.RunPython(copy_subtype_rows, uncopy_subtype_rows),
        migrations.RunPython(delete_microducts, migrations.RunPython.noop),
    ]
