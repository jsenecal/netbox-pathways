"""Tests for the FR#4 status addition: StructureStatusChoices.STATUS_ABANDONED."""

from netbox_pathways.choices import StructureStatusChoices


class TestAbandonedStatus:
    def test_status_value_present(self):
        assert StructureStatusChoices.STATUS_ABANDONED == "abandoned"

    def test_status_label_is_abandoned_in_place(self):
        labels = {value: label for value, label, *_ in StructureStatusChoices.CHOICES}
        assert labels.get("abandoned") == "Abandoned in place"

    def test_status_has_color(self):
        colors = StructureStatusChoices.colors
        assert colors.get("abandoned") == "gray"


def test_pathway_geometry_field_named_geometry():
    """The pathway geometry is `geometry`, freeing `path` for the ltree column (#177)."""
    from django.contrib.gis.db.models import LineStringField
    from netbox.models.ltree import LtreeField

    from netbox_pathways.models import Pathway

    assert isinstance(Pathway._meta.get_field("geometry"), LineStringField)
    assert isinstance(Pathway._meta.get_field("path"), LtreeField)
