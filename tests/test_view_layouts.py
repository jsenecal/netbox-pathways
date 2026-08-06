"""Tests for detail-view layout panel configuration."""

from netbox.ui.panels import ObjectsTablePanel

from netbox_pathways import views


def _iter_panels(layout):
    for row in layout:
        for column in row:
            yield from column


def test_conduit_bank_conduits_panel_swaps_bank_column_for_position():
    """The Conduits table embedded in a conduit bank's detail page hides
    the redundant conduit_bank column (it links back to the page being
    viewed) and shows bank_position instead. Regression test for #76."""
    panel = next(
        p
        for p in _iter_panels(views.ConduitBankView.layout)
        if isinstance(p, ObjectsTablePanel) and p.model_label == "netbox_pathways.Conduit"
    )
    assert "conduit_bank" in panel.exclude_columns
    assert "bank_position" in panel.include_columns
