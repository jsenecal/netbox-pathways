"""Tests for plugin-owned signal handlers."""

import pytest
from django.contrib.gis.geos import LineString, Point
from django.core.exceptions import ValidationError

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Pathway, Structure
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="SIG-site", slug="sig-site")


@pytest.fixture
def cable_and_pathway(db):
    from dcim.models import Cable

    s1 = Structure.objects.create(name="SA", location=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="SB", location=Point(100, 0, srid=SRID))
    pw = Pathway.objects.create(
        label="P1",
        pathway_type="conduit",
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=s1,
        end_structure=s2,
    )
    cable = Cable.objects.create()
    return cable, pw, s1, s2


@pytest.fixture
def pathway(db):
    s1 = Structure.objects.create(name="SP-A", location=Point(0, 0, srid=SRID))
    s2 = Structure.objects.create(name="SP-B", location=Point(100, 0, srid=SRID))
    return Pathway.objects.create(
        label="P-sig",
        pathway_type="conduit",
        path=LineString((0, 0), (100, 0), srid=SRID),
        start_structure=s1,
        end_structure=s2,
    )


@pytest.mark.django_db
class TestEnforceCableRoutability:
    def test_no_cable_id_skips_check(self, cable_and_pathway):
        """When instance.cable_id is None, the signal returns without raising."""
        _, pw, _, _ = cable_and_pathway
        seg = CableSegment(cable=None, pathway=pw, sequence=1)
        from netbox_pathways.signals import enforce_cable_routability

        # Should not raise -- signal short-circuits on falsy cable_id.
        enforce_cable_routability(sender=CableSegment, instance=seg)

    def test_both_terminations_pass(self, site, pathway):
        """When the cable has both A and B terminations, save succeeds."""
        cable = build_cable_with_terminations(
            label="SIG-both",
            site=site,
            terminate_a=True,
            terminate_b=True,
        )
        seg = CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)
        assert seg.pk is not None

    def test_missing_a_termination_raises(self, site, pathway):
        """When only B is wired, the signal raises ValidationError."""
        cable = build_cable_with_terminations(
            label="SIG-b-only",
            site=site,
            terminate_a=False,
            terminate_b=True,
        )
        with pytest.raises(ValidationError, match="A and B terminations"):
            CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

    def test_missing_b_termination_raises(self, site, pathway):
        """When only A is wired, the signal raises ValidationError."""
        cable = build_cable_with_terminations(
            label="SIG-a-only",
            site=site,
            terminate_a=True,
            terminate_b=False,
        )
        with pytest.raises(ValidationError, match="A and B terminations"):
            CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

    def test_no_terminations_raises(self, cable_and_pathway):
        """When neither A nor B is wired, the signal raises ValidationError."""
        cable, pw, _, _ = cable_and_pathway
        with pytest.raises(ValidationError, match="A and B terminations"):
            CableSegment.objects.create(cable=cable, pathway=pw, sequence=1)
