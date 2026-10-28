"""Copy the subtype rows onto Pathway; fix up rows the new rules reject.

Retired microduct rows are deleted. Base-only rows the old generic API
created as an innerduct with no parent keep everything but their type,
which is cleared so the parent constraint added next does not abort the
upgrade.

The work is done by tested helpers in netbox_pathways.upgrade. Deleting
microducts and clearing types cannot be reversed; reversing the copy
rebuilds the child rows.
"""

from django.db import migrations

from netbox_pathways.upgrade import (
    copy_subtype_rows,
    delete_microducts,
    uncopy_subtype_rows,
    untype_parentless_rows,
)


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0028_pathway_flatten_columns"),
    ]

    operations = [
        migrations.RunPython(copy_subtype_rows, uncopy_subtype_rows),
        migrations.RunPython(delete_microducts, migrations.RunPython.noop),
        migrations.RunPython(untype_parentless_rows, migrations.RunPython.noop),
    ]
