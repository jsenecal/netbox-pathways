"""Tenant plumbing on every pathway type.

Issue #168 found innerducts (and, for the edit/bulk-edit/filter surfaces,
conduits, aerial spans and direct buried) missing ``tenant``, so it could only
be set through the base pathways endpoint or CSV import. With one pathway
form the remaining risk is the form dropping ``tenant`` for some type.
"""

import pytest

from netbox_pathways import filterforms, forms
from netbox_pathways.choices import PathwayTypeChoices


@pytest.mark.django_db
@pytest.mark.parametrize("pathway_type", PathwayTypeChoices.values())
def test_edit_form_has_tenant_for_every_type(pathway_type):
    form = forms.PathwayForm(initial={"pathway_type": pathway_type})
    assert "tenant" in form.fields
    assert any("tenant" in fs.items for fs in form.fieldsets)


def test_bulk_edit_form_can_set_and_clear_tenant():
    assert "tenant" in forms.PathwayBulkEditForm.base_fields
    assert "tenant" in forms.PathwayBulkEditForm.nullable_fields


def test_filter_form_has_tenant():
    form = filterforms.PathwayFilterForm
    assert "tenant_id" in form.base_fields
    assert any("tenant_id" in fs.items for fs in form.fieldsets)
