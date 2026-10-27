"""Tests for detail-view layout panel configuration."""

from netbox.ui.panels import ObjectsTablePanel

from netbox_pathways import views


def _conduits_panel():
    return next(
        panel
        for row in views.ConduitBankView.layout
        for column in row
        for panel in column
        if isinstance(panel, ObjectsTablePanel) and panel.model_label == "netbox_pathways.Conduit"
    )


def test_conduit_bank_conduits_panel_swaps_bank_column_for_position():
    """The Conduits table embedded in a conduit bank's detail page hides
    the redundant conduit_bank column (it links back to the page being
    viewed) and shows bank_position instead. Regression test for #76."""
    panel = _conduits_panel()
    assert panel.include_columns == ["bank_position"]
    assert panel.exclude_columns == ["conduit_bank"]
