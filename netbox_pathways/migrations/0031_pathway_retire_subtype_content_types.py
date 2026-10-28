"""Move history, tags, permissions and custom fields off the subtype content types.

The five subtype models are gone, but rows across NetBox still name their
content types: change log, tags, journal entries, bookmarks, custom field
and export template assignments, object permissions. This moves them onto
`netbox_pathways.pathway` and deletes the subtype content types.

!!! OPERATOR NOTE !!!
An object permission on a subtype becomes a new permission on pathway named
"<name> (pathways)", restricted to the types it covered. A constraint that
cannot be translated aborts the migration with the permission listed; fix or
remove it and migrate again. Custom field `unique` and `required` flags the
merged pathway model cannot honour are cleared and printed.

The reverse is a no-op: the subtype content types are not recreated.
"""

from django.db import migrations

from netbox_pathways.upgrade import retire_subtype_content_types


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("core", "0026_populate_job_execution_time"),
        ("extras", "0144_customfield_status"),
        ("users", "0016_default_ordering_indexes"),
        ("netbox_pathways", "0030_pathway_drop_subtypes"),
    ]

    operations = [
        migrations.RunPython(retire_subtype_content_types, migrations.RunPython.noop),
    ]
