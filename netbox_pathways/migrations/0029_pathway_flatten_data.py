"""Copy the subtype rows onto Pathway; delete rows the new table cannot hold.

Those are retired microduct rows, and base-only rows the old generic API
created as an innerduct with no parent or with no type at all.

The work is done by tested helpers in netbox_pathways.upgrade. Deleting
rows cannot be reversed; reversing the copy rebuilds the child rows.
"""

from django.db import migrations

from netbox_pathways.upgrade import (
    copy_subtype_rows,
    delete_microducts,
    delete_unrepresentable_rows,
    uncopy_subtype_rows,
)


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0028_pathway_flatten_columns"),
    ]

    operations = [
        migrations.RunPython(copy_subtype_rows, uncopy_subtype_rows),
        migrations.RunPython(delete_microducts, migrations.RunPython.noop),
        migrations.RunPython(delete_unrepresentable_rows, migrations.RunPython.noop),
    ]
