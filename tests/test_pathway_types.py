"""Tests for the pathway type metadata module (pathway_types.py)."""

import pytest

from netbox_pathways.choices import PathwayTypeChoices
from netbox_pathways.pathway_types import (
    DRAWN_TYPES,
    PATHWAY_TYPES,
    TYPE_SPECIFIC_FIELDS,
    allowed_child_types,
    inapplicable_fields,
    spec,
)


def test_types_match_choices():
    choice_values = {value for value, *_ in PathwayTypeChoices.CHOICES}
    assert set(PATHWAY_TYPES) == choice_values
    assert "microduct" not in choice_values


@pytest.mark.parametrize(
    ("parent", "expected"),
    [
        ("conduit_bank", {"conduit"}),
        ("raceway", {"conduit", "tray"}),
        ("tray", {"innerduct"}),
        ("conduit", {"innerduct"}),
        ("innerduct", {"innerduct"}),
        ("direct_buried", {"innerduct"}),
        ("aerial", set()),
        ("submarine", set()),
        ("", set()),
    ],
)
def test_containment_rule(parent, expected):
    assert allowed_child_types(parent) == frozenset(expected)


def test_only_innerduct_requires_parent():
    assert {t for t, s in PATHWAY_TYPES.items() if s.parent_required} == {"innerduct"}


def test_drawn_types():
    assert DRAWN_TYPES == {"conduit_bank", "conduit", "aerial", "direct_buried", "submarine"}


def test_inapplicable_fields_for_innerduct():
    fields = inapplicable_fields("innerduct")
    assert "material" in fields
    assert "size" not in fields
    assert "position" not in fields
    assert fields.isdisjoint(spec("innerduct").fields)
    assert fields <= TYPE_SPECIFIC_FIELDS


def test_spec_rejects_unknown_type():
    with pytest.raises(KeyError):
        spec("microduct")
