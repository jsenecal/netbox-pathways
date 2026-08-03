"""Store Innerduct.color as a palette hex code instead of free text (issue #79).

The old field accepted any 50-character string, so existing rows hold color
names. They are translated to the matching hex code before the column is
narrowed to six characters; anything that matches no known color is cleared
and reported, since it cannot survive the narrower column.
"""

import utilities.fields
from django.db import migrations
from netbox.choices import ColorChoices

# netbox_pathways.colors is a pure name-to-hex lookup with no model imports.
# It is safe to call from a migration: on a fresh database this data pass is
# a no-op, so later edits to the lookup cannot change what already ran.
from netbox_pathways.colors import color_to_hex

_NAME_BY_HEX = {value: str(label) for value, label in ColorChoices.CHOICES}


def color_names_to_hex(apps, schema_editor):
    Innerduct = apps.get_model("netbox_pathways", "Innerduct")
    existing = set(Innerduct.objects.exclude(color="").values_list("color", flat=True))
    dropped = []
    for color in existing:
        hex_code = color_to_hex(color)
        if hex_code is None:
            dropped.append(color)
            hex_code = ""
        if hex_code != color:
            Innerduct.objects.filter(color=color).update(color=hex_code)
    if dropped:
        print(
            f"\n  netbox_pathways: cleared {len(dropped)} unrecognized innerduct "
            f"color(s): {', '.join(sorted(dropped))}"
        )


def hex_to_color_names(apps, schema_editor):
    """Restore palette names; hex codes outside the palette are left as-is."""
    Innerduct = apps.get_model("netbox_pathways", "Innerduct")
    for hex_code, name in _NAME_BY_HEX.items():
        Innerduct.objects.filter(color=hex_code).update(color=name.lower())


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0021_structure_geometry_and_location"),
    ]

    operations = [
        migrations.RunPython(color_names_to_hex, hex_to_color_names),
        migrations.AlterField(
            model_name="innerduct",
            name="color",
            field=utilities.fields.ColorField(
                blank=True,
                help_text="Innerduct color for identification",
                max_length=6,
            ),
        ),
    ]
