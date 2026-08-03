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
