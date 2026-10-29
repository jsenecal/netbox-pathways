"""Add the flattened per-type columns and the hierarchy to Pathway.

First step of replacing the five multi-table-inheritance pathway subtypes
with one table. The child columns that move onto Pathway under the same name
are renamed to legacy_<name> first, because a child model may not shadow a
parent field; 0029 copies the values across and 0030 drops the child tables.

The junction foreign keys are repointed at Pathway here, before any data
moves, so that reversing the chain can put them back only after the conduit
rows exist again.
"""

import django.db.models.deletion
import netbox.models.ltree
import utilities.fields
from django.db import migrations, models

from netbox_pathways.upgrade import LEGACY_RENAMED_FIELDS


class Migration(migrations.Migration):
    dependencies = [
        ("dcim", "0242_ltree_paths"),
        ("netbox_pathways", "0027_rename_pathway_path_geometry"),
    ]

    operations = [
        migrations.RemoveIndex(model_name="conduit", name="netbox_path_materia_aa3008_idx"),
        migrations.RemoveIndex(model_name="aerialspan", name="netbox_path_aerial__66af78_idx"),
        *[
            migrations.RenameField(model_name=model_name, old_name=name, new_name=f"legacy_{name}")
            for model_name, names in LEGACY_RENAMED_FIELDS.items()
            for name in names
        ],
        # Free the reverse accessors for the same-named Pathway fields.
        *[
            migrations.AlterField(
                model_name="conduit",
                name=f"legacy_{side}_junction",
                field=models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+",
                    to="netbox_pathways.conduitjunction",
                ),
            )
            for side in ("start", "end")
        ],
        migrations.AlterField(
            model_name="conduitjunction",
            name="trunk_conduit",
            field=models.ForeignKey(
                limit_choices_to={"pathway_type": "conduit"},
                on_delete=django.db.models.deletion.CASCADE,
                related_name="junctions_on_trunk",
                to="netbox_pathways.pathway",
            ),
        ),
        migrations.AlterField(
            model_name="conduitjunction",
            name="branch_conduit",
            field=models.ForeignKey(
                limit_choices_to={"pathway_type": "conduit"},
                on_delete=django.db.models.deletion.CASCADE,
                related_name="junction_as_branch",
                to="netbox_pathways.pathway",
            ),
        ),
        migrations.AlterField(
            model_name="pathway",
            name="pathway_type",
            field=models.CharField(max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                help_text="Pathway this one runs inside (e.g. the bank of a conduit, the conduit of an innerduct)",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="children",
                to="netbox_pathways.pathway",
            ),
        ),
        # Nullable until 0030 installs the triggers and backfills it.
        migrations.AddField(
            model_name="pathway",
            name="path",
            field=netbox.models.ltree.LtreeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="pathway",
            name="start_face",
            field=models.CharField(blank=True, help_text="Which face/wall of the start structure", max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="end_face",
            field=models.CharField(blank=True, help_text="Which face/wall of the end structure", max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="configuration",
            field=models.CharField(
                blank=True,
                help_text="Layout configuration (e.g., 2x2, 3x3) -- leave blank if irregular",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="total_conduits",
            field=models.PositiveIntegerField(
                blank=True, help_text="Designed conduit capacity of the bank (leave blank if unknown)", null=True
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="height",
            field=models.PositiveIntegerField(
                blank=True, help_text="Number of duct rows (vertical count); leave blank if unknown", null=True
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="width",
            field=models.PositiveIntegerField(
                blank=True, help_text="Number of duct columns (horizontal count); leave blank if unknown", null=True
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="encasement_type",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="material",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="inner_diameter",
            field=models.FloatField(blank=True, help_text="Inner diameter in millimeters", null=True),
        ),
        migrations.AddField(
            model_name="pathway",
            name="outer_diameter",
            field=models.FloatField(blank=True, help_text="Outer diameter in millimeters", null=True),
        ),
        migrations.AddField(
            model_name="pathway",
            name="depth",
            field=models.FloatField(blank=True, help_text="Burial depth in meters", null=True),
        ),
        migrations.AddField(
            model_name="pathway",
            name="start_junction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conduits_from",
                to="netbox_pathways.conduitjunction",
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="end_junction",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="conduits_to",
                to="netbox_pathways.conduitjunction",
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="position",
            field=models.CharField(
                blank=True, help_text="Position within the parent pathway (e.g., A1 in a bank)", max_length=50
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="aerial_type",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="start_attachment_height",
            field=models.FloatField(
                blank=True, help_text="Attachment height at the start endpoint, in meters", null=True
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="end_attachment_height",
            field=models.FloatField(
                blank=True, help_text="Attachment height at the end endpoint, in meters", null=True
            ),
        ),
        migrations.AddField(
            model_name="pathway",
            name="sag",
            field=models.FloatField(blank=True, help_text="Cable sag in meters", null=True),
        ),
        migrations.AddField(
            model_name="pathway",
            name="messenger_size",
            field=models.CharField(blank=True, help_text="Messenger wire size/type", max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="wind_loading",
            field=models.CharField(blank=True, help_text="Wind loading zone/rating", max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="ice_loading",
            field=models.CharField(blank=True, help_text="Ice loading zone/rating", max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="burial_depth",
            field=models.FloatField(blank=True, help_text="Burial depth in meters", null=True),
        ),
        migrations.AddField(
            model_name="pathway",
            name="warning_tape",
            field=models.BooleanField(default=False, help_text="Warning tape installed above cable"),
        ),
        migrations.AddField(
            model_name="pathway",
            name="tracer_wire",
            field=models.BooleanField(default=False, help_text="Tracer wire installed with cable"),
        ),
        migrations.AddField(
            model_name="pathway",
            name="armor_type",
            field=models.CharField(blank=True, help_text="Cable armor type if applicable", max_length=100),
        ),
        migrations.AddField(
            model_name="pathway",
            name="size",
            field=models.CharField(blank=True, help_text='Innerduct size (e.g., 1.25", 32mm)', max_length=50),
        ),
        migrations.AddField(
            model_name="pathway",
            name="color",
            field=utilities.fields.ColorField(blank=True, help_text="Innerduct color for identification", max_length=6),
        ),
        migrations.AddIndex(
            model_name="pathway",
            index=models.Index(fields=["material"], name="netbox_path_materia_d7af4d_idx"),
        ),
        migrations.AddIndex(
            model_name="pathway",
            index=models.Index(fields=["aerial_type"], name="netbox_path_aerial__27cf6b_idx"),
        ),
    ]
