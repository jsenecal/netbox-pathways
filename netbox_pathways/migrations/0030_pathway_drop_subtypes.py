"""Drop the pathway subtype tables and turn Pathway into an ltree hierarchy.

Follows NetBox core's dcim 0242_ltree_paths: install the path triggers,
backfill `path` for existing rows with one recursive CTE, fail loudly if any
row was missed, then make the column NOT NULL. The ltree extension itself is
created by that core migration, which this chain depends on.

!!! OPERATOR NOTE !!!
The backfill is a single UPDATE over every pathway row and holds a row lock
on the table for its duration.
"""

import netbox.models.ltree
from django.contrib.postgres.indexes import GistIndex
from django.db import migrations, models
from utilities.ltree import InstallLtreeTriggers
from utilities.mptt_to_ltree import assert_paths_populated_sql, populate_paths_sql

TABLE = "netbox_pathways_pathway"


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0242_ltree_paths"),
        ("netbox_pathways", "0029_pathway_flatten_data"),
    ]

    operations = [
        migrations.DeleteModel(name="Innerduct"),
        migrations.DeleteModel(name="Conduit"),
        migrations.DeleteModel(name="ConduitBank"),
        migrations.DeleteModel(name="AerialSpan"),
        migrations.DeleteModel(name="DirectBuried"),
        migrations.AddConstraint(
            model_name="pathway",
            constraint=models.CheckConstraint(
                condition=models.Q(("pathway_type__in", ["innerduct"]), _negated=True)
                | models.Q(("parent__isnull", False)),
                name="pathway_parent_required",
                violation_error_message="This pathway type must have a parent.",
            ),
        ),
        migrations.AddConstraint(
            model_name="pathway",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("pathway_type__in", ["aerial", "conduit_bank", "direct_buried", "raceway", "submarine"]),
                    _negated=True,
                )
                | models.Q(("parent__isnull", True)),
                name="pathway_parent_forbidden",
                violation_error_message="This pathway type cannot have a parent.",
            ),
        ),
        migrations.AddConstraint(
            model_name="pathway",
            constraint=models.UniqueConstraint(
                condition=models.Q(("parent__isnull", False), ("pathway_type", "conduit"), ("position__gt", "")),
                fields=("parent", "position"),
                name="unique_conduit_position_in_parent",
                violation_error_message="Another conduit already occupies this position in the parent.",
            ),
        ),
        InstallLtreeTriggers(TABLE),
        migrations.RunSQL(populate_paths_sql(TABLE), reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(assert_paths_populated_sql(TABLE), reverse_sql=migrations.RunSQL.noop),
        migrations.AlterField(
            model_name="pathway",
            name="path",
            field=netbox.models.ltree.LtreeField(blank=True, default="", editable=False),
        ),
        migrations.AddIndex(
            model_name="pathway",
            index=GistIndex(fields=["path"], name="netbox_path_pathway_path_gist"),
        ),
    ]
