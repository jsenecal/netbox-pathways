"""The pathway filter form's per-type fieldsets come from pathway_types.py."""

from netbox_pathways.choices import PathwayTypeChoices
from netbox_pathways.filterforms import PathwayFilterForm
from netbox_pathways.pathway_types import PATHWAY_TYPES, TYPE_SPECIFIC_FIELDS

TYPE_LABELS = {value: label for value, label, *_ in PathwayTypeChoices.CHOICES}


def _items(fieldset):
    return list(fieldset.items)


def test_no_field_is_rendered_twice():
    """A field in two fieldsets renders two inputs and submits its value twice."""
    items = [item for fieldset in PathwayFilterForm.fieldsets for item in _items(fieldset)]
    assert len(items) == len(set(items))


def test_type_fieldsets_hold_only_that_types_fields():
    by_label = {str(fieldset.name): _items(fieldset) for fieldset in PathwayFilterForm.fieldsets}
    type_fieldsets = {t: by_label[TYPE_LABELS[t]] for t in PATHWAY_TYPES if TYPE_LABELS[t] in by_label}
    assert type_fieldsets
    for pathway_type, items in type_fieldsets.items():
        assert set(items) <= set(PATHWAY_TYPES[pathway_type].fields), pathway_type


def test_every_rendered_type_field_is_a_form_field():
    rendered = {item for fieldset in PathwayFilterForm.fieldsets for item in _items(fieldset)}
    form_fields = set(PathwayFilterForm.base_fields)
    assert rendered & TYPE_SPECIFIC_FIELDS <= form_fields
