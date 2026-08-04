import pytest
from dcim.models import Cable
from django.contrib.gis.geos import LineString, Point

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Conduit, Pathway, Structure
from netbox_pathways.routing import validate_cable_route
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.mark.django_db
class TestValidateCableRoute:
    @pytest.fixture(autouse=True)
    def _disable_routability_signal(self):
        """Disable routability signal for route validation tests (no terminations needed)."""
        from django.db.models.signals import pre_save

        from netbox_pathways.signals import enforce_cable_routability

        pre_save.disconnect(enforce_cable_routability, sender=CableSegment)
        yield
        pre_save.connect(enforce_cable_routability, sender=CableSegment)

    @pytest.fixture
    def srid(self):
        return get_srid()

    @pytest.fixture
    def structures(self, srid):
        return [
            Structure.objects.create(
                name=f"MH-R-{i}",
                geometry=Point(i, i, srid=srid),
            )
            for i in range(4)
        ]

    @pytest.fixture
    def cable(self):
        return Cable.objects.create(label="CABLE-R-001")

    def _make_conduit(self, label, s_from, s_to, srid):
        return Conduit.objects.create(
            label=label,
            start_structure=s_from,
            end_structure=s_to,
            path=LineString((0, 0), (1, 1), srid=srid),
        )

    def test_no_segments(self, cable):
        result = validate_cable_route(cable.pk)
        assert result["segment_count"] == 0
        assert result["valid"] is False

    def test_single_segment_valid(self, cable, structures, srid):
        pw = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        CableSegment.objects.create(cable=cable, pathway=pw)
        result = validate_cable_route(cable.pk)
        assert result["valid"] is True
        assert result["gaps"] == []

    def test_connected_route_valid(self, cable, structures, srid):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        pw2 = self._make_conduit("C-R-2", structures[1], structures[2], srid)
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=pw2)
        result = validate_cable_route(cable.pk)
        assert result["valid"] is True
        assert result["gaps"] == []

    def test_gap_detected(self, cable, structures, srid):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        pw2 = self._make_conduit("C-R-2", structures[2], structures[3], srid)
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=pw2)
        result = validate_cable_route(cable.pk)
        assert result["valid"] is False
        assert len(result["gaps"]) == 1

    def test_segment_with_null_pathway(self, cable, structures, srid):
        pw1 = self._make_conduit("C-R-1", structures[0], structures[1], srid)
        CableSegment.objects.create(cable=cable, pathway=pw1)
        CableSegment.objects.create(cable=cable, pathway=None)
        result = validate_cable_route(cable.pk)
        assert result["valid"] is False
        assert len(result["gaps"]) == 1


@pytest.mark.django_db
class TestRouteEndChecks:
    """`valid` means "no gaps"; `ends` says whether the route reaches the cable."""

    def test_ok_when_the_first_segment_touches_the_a_candidates(self, db):
        from dcim.models import Site

        site = Site.objects.create(name="RE-ok", slug="re-ok")
        a = Structure.objects.create(name="RE-a", site=site, geometry=Point(0, 0, srid=SRID))
        b = Structure.objects.create(name="RE-b", site=site, geometry=Point(100, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RE-P1",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=a,
            end_structure=b,
        )
        cable = build_cable_with_terminations(label="RE-cable-ok", site=site)
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

        result = validate_cable_route(cable.pk)
        assert result["ends"] == {"a": "ok", "b": "ok"}

    def test_mismatch_when_the_route_starts_somewhere_else(self, db):
        from dcim.models import Site

        site = Site.objects.create(name="RE-mm", slug="re-mm")
        Structure.objects.create(name="RE-anchor", site=site, geometry=Point(0, 0, srid=SRID))
        far_a = Structure.objects.create(name="RE-far-a", geometry=Point(500, 0, srid=SRID))
        far_b = Structure.objects.create(name="RE-far-b", geometry=Point(600, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RE-P2",
            pathway_type="conduit",
            path=LineString((500, 0), (600, 0), srid=SRID),
            start_structure=far_a,
            end_structure=far_b,
        )
        cable = build_cable_with_terminations(label="RE-cable-mm", site=site)
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

        result = validate_cable_route(cable.pk)
        assert result["valid"] is True  # no gaps -- unchanged semantics
        assert result["ends"] == {"a": "mismatch", "b": "mismatch"}

    def test_unverified_when_the_cable_end_is_not_in_the_plant(self, db):
        from dcim.models import Site

        site = Site.objects.create(name="RE-un", slug="re-un")
        a = Structure.objects.create(name="RE-un-a", geometry=Point(0, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RE-P3",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=a,
        )
        cable = build_cable_with_terminations(label="RE-cable-un", site=site)
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

        assert validate_cable_route(cable.pk)["ends"] == {"a": "unverified", "b": "unverified"}

    def test_unverified_when_there_are_no_segments(self, db):
        from dcim.models import Site

        site = Site.objects.create(name="RE-none", slug="re-none")
        cable = build_cable_with_terminations(label="RE-cable-none", site=site)
        assert validate_cable_route(cable.pk)["ends"] == {"a": "unverified", "b": "unverified"}
