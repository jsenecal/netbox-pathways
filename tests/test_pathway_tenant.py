"""Tenant plumbing parity across the concrete pathway types.

Every pathway type inherits ``tenant`` from ``Pathway``; issue #168 found
innerducts (and, for the edit/bulk-edit/filter surfaces, conduits, aerial
spans and direct buried) missing it, so it could only be set through the base
pathways endpoint or CSV import.
"""

import pytest
from tenancy.models import Tenant

from netbox_pathways import filterforms, filtersets, forms
from netbox_pathways.api import serializers
from netbox_pathways.models import AerialSpan, Conduit, DirectBuried, Innerduct

PATHWAY_TYPES = ["Conduit", "AerialSpan", "DirectBuried", "Innerduct"]


@pytest.mark.parametrize("name", PATHWAY_TYPES)
def test_serializer_exposes_writable_tenant(name):
    field = getattr(serializers, f"{name}Serializer")().fields["tenant"]
    assert not field.read_only


@pytest.mark.parametrize("name", PATHWAY_TYPES)
def test_edit_form_has_tenant(name):
    form = getattr(forms, f"{name}Form")
    assert "tenant" in form.base_fields
    assert any("tenant" in fs.items for fs in form.fieldsets)


@pytest.mark.parametrize("name", PATHWAY_TYPES)
def test_bulk_edit_form_can_set_and_clear_tenant(name):
    form = getattr(forms, f"{name}BulkEditForm")
    assert "tenant" in form.base_fields
    assert "tenant" in form.nullable_fields


@pytest.mark.parametrize("name", PATHWAY_TYPES)
def test_filter_form_has_tenant(name):
    form = getattr(filterforms, f"{name}FilterForm")
    assert "tenant_id" in form.base_fields
    assert any("tenant_id" in fs.items for fs in form.fieldsets)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,filterset",
    [
        (Conduit, filtersets.ConduitFilterSet),
        (AerialSpan, filtersets.AerialSpanFilterSet),
        (DirectBuried, filtersets.DirectBuriedFilterSet),
        (Innerduct, filtersets.InnerductFilterSet),
    ],
)
def test_filterset_filters_by_tenant(model, filterset):
    owner = Tenant.objects.create(name="Owner", slug="owner")
    other = Tenant.objects.create(name="Other", slug="other")
    kwargs = {"parent_conduit": Conduit.objects.create(label="parent")} if model is Innerduct else {}
    mine = model.objects.create(label="mine", tenant=owner, **kwargs)
    model.objects.create(label="theirs", tenant=other, **kwargs)

    qs = model.objects.filter(label__in=["mine", "theirs"])
    assert list(filterset({"tenant_id": [owner.pk]}, qs).qs) == [mine]
    assert list(filterset({"tenant": [owner.slug]}, qs).qs) == [mine]
