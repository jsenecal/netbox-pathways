"""Tests for the Pathway.status field (issue #60) -- plugin-owned behavior only."""

from netbox_pathways.choices import PathwayStatusChoices, StructureStatusChoices
from netbox_pathways.models import Conduit


def test_pathway_status_choices_mirror_structure_status_choices():
    """Issue #60 asks for the same status options as structures."""
    assert PathwayStatusChoices.values() == StructureStatusChoices.values()


def test_pathway_get_status_color():
    """Pathway defines get_status_color() itself; the badge templates call it."""
    conduit = Conduit(label="status-color", status=PathwayStatusChoices.STATUS_RETIRED)
    assert conduit.get_status_color() == PathwayStatusChoices.colors["retired"]
