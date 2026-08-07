"""Tests for detail-view layout panel configuration."""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from netbox.ui.panels import ObjectsTablePanel

from netbox_pathways import views
from netbox_pathways.models import Conduit
from netbox_pathways.tables import ConduitTable


def _iter_panels(layout):
    for row in layout:
        for column in row:
            yield from column


def _conduits_panel():
    return next(
        p
        for p in _iter_panels(views.ConduitBankView.layout)
        if isinstance(p, ObjectsTablePanel) and p.model_label == "netbox_pathways.Conduit"
    )


def test_conduit_bank_conduits_panel_swaps_bank_column_for_position():
    """The Conduits table embedded in a conduit bank's detail page hides
    the redundant conduit_bank column (it links back to the page being
    viewed) and shows bank_position instead. The overrides travel as URL
    params via `filters` rather than the panel's include_columns /
    exclude_columns kwargs, which NetBox 4.5 does not accept. Regression
    test for #76."""
    panel = _conduits_panel()
    assert panel.filters.get("include_columns") == "bank_position"
    assert panel.filters.get("exclude_columns") == "conduit_bank"


@pytest.mark.django_db
def test_conduit_table_configure_applies_column_override_params():
    """NetBox 4.5 ignores the include_columns/exclude_columns URL params
    that 4.6 applies in NetBoxTable.configure(), so ConduitTable backports
    the handling. On 4.6 this exercises the idempotent overlap of the
    backport and core. Regression test for the #76 CI failure on the
    4.5.x matrix."""
    request = RequestFactory().get(
        "/",
        {"include_columns": "bank_position", "exclude_columns": "conduit_bank"},
    )
    request.user = AnonymousUser()
    table = ConduitTable(Conduit.objects.none())
    table.configure(request)
    visible = [column.name for column in table.columns if column.visible]
    assert "bank_position" in visible
    assert "conduit_bank" not in visible
