"""Tests for the pathway detail page's panels."""

import pytest
from django.test import RequestFactory
from netbox.ui.panels import ObjectsTablePanel

from netbox_pathways import views
from netbox_pathways.models import Pathway
from netbox_pathways.pathway_types import TYPE_SPECIFIC_FIELDS
from netbox_pathways.ui.panels import PathwayTypePanel


def _children_panel():
    return next(
        panel
        for row in views.PathwayView.layout
        for column in row
        for panel in column
        if isinstance(panel, ObjectsTablePanel) and panel.title == "Children"
    )


def test_children_panel_swaps_parent_column_for_position():
    """The children table on a pathway's page hides the parent column (it
    links back to the page being viewed) and shows each child's position.
    Regression test for #76, which asked this of a bank's conduits."""
    panel = _children_panel()
    assert panel.include_columns == ["position"]
    assert panel.exclude_columns == ["parent"]


@pytest.mark.parametrize(
    "pathway_type, expected",
    [("conduit_bank", True), ("conduit", True), ("raceway", True), ("aerial", False), ("submarine", False)],
)
def test_children_panel_only_on_types_that_contain_others(pathway_type, expected):
    context = {"object": Pathway(pathway_type=pathway_type), "request": None}
    assert _children_panel().should_render(context) is expected


@pytest.mark.parametrize(
    "pathway_type, add_preset",
    [("conduit_bank", "conduit"), ("conduit", "innerduct"), ("raceway", "")],
)
def test_add_child_presets_the_only_type_the_parent_may_contain(pathway_type, add_preset):
    assert views._only_child_type(Pathway(pathway_type=pathway_type)) == add_preset


def _type_panel_context(pathway):
    panel = PathwayTypePanel()
    request = RequestFactory().get("/")
    return panel, panel.get_context({"object": pathway, "request": request, "perms": None})


def test_type_panel_shows_only_the_types_own_attributes():
    """An aerial span shows its heights and sag (and the mean height computed from them), not conduit sizes."""
    panel, ctx = _type_panel_context(Pathway(pathway_type="aerial", sag=1.5))

    labels = [attr["label"] for attr in ctx["attrs"]]
    assert "Sag (m)" in labels
    assert "Attachment height (mean, m)" in labels
    assert "Inner diameter (mm)" not in labels
    assert ctx["title"] == "Aerial Span"
    assert panel.should_render(ctx)


def test_type_panel_declares_every_type_specific_field():
    """A field missing from the panel would silently never show on any pathway's page."""
    assert TYPE_SPECIFIC_FIELDS <= set(PathwayTypePanel._attrs)


def test_type_panel_is_hidden_for_types_without_attributes():
    panel, ctx = _type_panel_context(Pathway(pathway_type="submarine"))
    assert ctx["attrs"] == []
    assert not panel.should_render(ctx)
