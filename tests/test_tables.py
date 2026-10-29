"""Row actions on every plugin table must point at views that exist.

Regression for issue #167: ``PathwayTable`` offered edit/delete for the base
``Pathway`` model, which has no such views, so the generic Pathways list
raised ``NoReverseMatch`` as soon as it rendered a row.
"""

import inspect

import pytest
from netbox.tables import NetBoxTable
from utilities.views import get_action_url

from netbox_pathways import tables
from netbox_pathways.pathway_types import TYPE_SPECIFIC_FIELDS

ACTION_TABLES = [
    cls
    for _, cls in inspect.getmembers(tables, inspect.isclass)
    if issubclass(cls, NetBoxTable) and cls.__module__ == tables.__name__ and "actions" in cls.base_columns
]


@pytest.mark.parametrize("table", ACTION_TABLES, ids=lambda t: t.__name__)
def test_row_actions_resolve(table):
    model = table._meta.model
    for action in table.base_columns["actions"].actions:
        get_action_url(model, action=action, kwargs={"pk": 1})


def test_pathway_table_has_a_column_for_every_type_specific_field():
    """One table lists every pathway type, so each type's own fields must be selectable columns."""
    assert TYPE_SPECIFIC_FIELDS <= set(tables.PathwayTable.base_columns)
