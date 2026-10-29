"""generate_sample_data: the steps that know about the pathway hierarchy."""

from io import StringIO

import pytest
from django.contrib.gis.geos import LineString

from netbox_pathways.management.commands.generate_sample_data import Command
from netbox_pathways.models import Pathway
from tests.helpers import SRID


def _command(out=None):
    return Command(stdout=out or StringIO())


def _top(pathway_type, label):
    return Pathway.objects.create(
        pathway_type=pathway_type, label=label, geometry=LineString((0, 0), (10, 0), srid=SRID), length=10
    )


@pytest.mark.django_db
def test_flush_clears_a_protected_hierarchy():
    """`parent` is PROTECT, so the flush has to delete from the leaves up."""
    bank = _top("conduit_bank", "GS-Bank")
    conduit = Pathway.objects.create(pathway_type="conduit", label="GS-Conduit", parent=bank)
    Pathway.objects.create(pathway_type="innerduct", label="GS-Duct", parent=conduit)

    _command()._flush()

    assert not Pathway.objects.exists()


@pytest.mark.django_db
def test_innerducts_hang_from_the_given_parents_without_geometry():
    parents = [_top("conduit", "GS-C"), _top("direct_buried", "GS-DB")]
    out = StringIO()
    command = _command(out)

    innerducts = command._create_innerducts(parents)

    assert {duct.parent_id for duct in innerducts} <= {p.pk for p in parents}
    assert not Pathway.objects.filter(pathway_type="innerduct", geometry__isnull=False).exists()
    command._print_counts()
    assert f"{'Innerducts:':<20}{len(innerducts)}" in out.getvalue()
