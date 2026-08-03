"""Tests for issue #79: Innerduct.color as a NetBox color choice.

The field used to be free text, so users typed color names by hand. It now
stores a 6-digit hex from NetBox's core palette and renders through the core
color widget and column. The name-to-hex helper is what keeps the legacy
values (and legacy CSV imports) working.
"""

import importlib

import pytest
from django.apps import apps as global_apps
from django.contrib.gis.geos import LineString, Point
from netbox.choices import ColorChoices
from netbox.tables import columns
from utilities.forms.widgets import ColorSelect

from netbox_pathways import filterforms, forms, models, tables
from netbox_pathways.colors import color_to_hex
from netbox_pathways.geo import get_srid

SRID = get_srid()


class TestColorToHex:
    """Legacy free-text values map onto the core palette where they can."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("blue", ColorChoices.COLOR_BLUE),
            ("Blue", ColorChoices.COLOR_BLUE),
            ("  ORANGE  ", ColorChoices.COLOR_ORANGE),
            ("dark green", ColorChoices.COLOR_DARK_GREEN),
            ("light grey", ColorChoices.COLOR_LIGHT_GREY),
        ],
    )
    def test_palette_labels_resolve(self, value, expected):
        assert color_to_hex(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            # The telecom 12-color code has two names the palette lacks.
            ("slate", ColorChoices.COLOR_DARK_GREY),
            ("violet", ColorChoices.COLOR_PURPLE),
            # US spelling, which the palette labels do not use.
            ("gray", ColorChoices.COLOR_GREY),
            ("dark gray", ColorChoices.COLOR_DARK_GREY),
        ],
    )
    def test_synonyms_resolve(self, value, expected):
        assert color_to_hex(value) == expected

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("ff9800", "ff9800"),
            ("#FF9800", "ff9800"),
            ("f00", "ff0000"),
        ],
    )
    def test_hex_values_pass_through_normalized(self, value, expected):
        assert color_to_hex(value) == expected

    def test_blank_stays_blank(self):
        assert color_to_hex("") == ""
        assert color_to_hex(None) == ""

    @pytest.mark.parametrize("value", ["mauve", "duct #4", "ggg", "12345"])
    def test_unrecognized_values_are_none(self, value):
        """None, not blank -- callers decide between dropping and rejecting."""
        assert color_to_hex(value) is None


class TestInnerductColorWiring:
    def test_edit_form_uses_the_core_color_widget(self, db):
        assert isinstance(forms.InnerductForm().fields["color"].widget, ColorSelect)

    def test_bulk_edit_form_uses_the_core_color_widget(self, db):
        assert isinstance(forms.InnerductBulkEditForm().fields["color"].widget, ColorSelect)

    def test_filter_form_uses_the_core_color_widget(self, db):
        assert isinstance(filterforms.InnerductFilterForm().fields["color"].widget, ColorSelect)

    def test_filter_form_exposes_every_innerduct_attribute_filter(self, db):
        """The filterset has always accepted these; the form omitted them."""
        rendered = {item for fieldset in filterforms.InnerductFilterForm.fieldsets for item in fieldset.items}
        assert {"size", "color", "position"} <= rendered

    def test_table_renders_color_as_a_swatch(self):
        assert isinstance(tables.InnerductTable.base_columns["color"], columns.ColorColumn)


class TestInnerductImportColor:
    """CSV import keeps accepting the color names it accepted before."""

    def test_a_color_name_is_stored_as_hex(self, db):
        form = forms.InnerductImportForm(data={"color": "Blue"})
        form.is_valid()  # other required fields are missing; only color matters here
        assert form.cleaned_data["color"] == ColorChoices.COLOR_BLUE

    def test_a_hex_code_is_accepted(self, db):
        form = forms.InnerductImportForm(data={"color": "2196f3"})
        form.is_valid()
        assert form.cleaned_data["color"] == ColorChoices.COLOR_BLUE

    def test_an_unrecognized_color_is_rejected(self, db):
        form = forms.InnerductImportForm(data={"color": "mauve"})
        form.is_valid()
        assert "color" in form.errors


class TestColorDataMigration:
    """Migration 0022 rewrites the free-text colors already in the table."""

    def test_names_become_hex_and_unknowns_are_cleared(self, db, capsys):
        conduit = models.Conduit.objects.create(
            label="color-migration-conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=models.Structure.objects.create(
                name="color-migration-start",
                geometry=Point(0, 0, srid=SRID),
            ),
            end_structure=models.Structure.objects.create(
                name="color-migration-end",
                geometry=Point(100, 0, srid=SRID),
            ),
        )
        # Values must fit the post-migration column, so keep them short.
        for index, color in enumerate(["orange", "blue", "mauve"]):
            models.Innerduct.objects.create(
                label=f"color-migration-{index}",
                parent_conduit=conduit,
                size="32mm",
                color=color,
            )

        migration = importlib.import_module("netbox_pathways.migrations.0022_innerduct_color_hex")
        migration.color_names_to_hex(global_apps, None)

        colors = dict(models.Innerduct.objects.values_list("label", "color"))
        assert colors["color-migration-0"] == ColorChoices.COLOR_ORANGE
        assert colors["color-migration-1"] == ColorChoices.COLOR_BLUE
        assert colors["color-migration-2"] == ""
        assert "mauve" in capsys.readouterr().out
