"""The Route tab states where each cable end sits, or why it cannot tell."""

import pytest
from django.contrib.gis.geos import LineString, Point
from django.test import RequestFactory

from netbox_pathways.geo import get_srid
from netbox_pathways.models import CableSegment, Pathway, Structure
from netbox_pathways.views import CableRouteView
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="RR-site", slug="rr-site")


@pytest.fixture
def bare_site(db):
    """A site with nothing modeled in Pathways -- an end that cannot be placed."""
    from dcim.models import Site

    return Site.objects.create(name="RR-bare", slug="rr-bare")


def _context(admin_user, cable):
    request = RequestFactory().get(f"/dcim/cables/{cable.pk}/route/")
    request.user = admin_user
    return CableRouteView().get_extra_context(request, cable)


@pytest.mark.django_db
class TestEndpointReadout:
    def test_resolved_ends_list_their_candidates(self, site, admin_user):
        Structure.objects.create(name="RR-mh", site=site, geometry=Point(0, 0, srid=SRID))
        cable = build_cable_with_terminations(label="RR-ok", site=site)
        endpoints = _context(admin_user, cable)["cable_endpoints"]
        assert [e["end"] for e in endpoints] == ["A", "B"]
        assert endpoints[0]["labels"] == ["RR-mh"]
        assert endpoints[0]["message"] is None

    def test_unresolved_end_states_the_reason_and_the_remedy(self, site, admin_user):
        cable = build_cable_with_terminations(label="RR-empty", site=site)
        endpoints = _context(admin_user, cable)["cable_endpoints"]
        assert endpoints[0]["labels"] == []
        assert site.name in endpoints[0]["message"]
        assert "Site Geometry" in endpoints[0]["remedy"]

    def test_one_unresolved_end_stays_visible_beside_a_resolved_one(self, site, bare_site, admin_user):
        """A good A end must not hide a B end nobody can place."""
        Structure.objects.create(name="RR-mixed-mh", site=site, geometry=Point(0, 0, srid=SRID))
        cable = build_cable_with_terminations(label="RR-mixed", site=site, site_b=bare_site)
        endpoints = _context(admin_user, cable)["cable_endpoints"]
        assert endpoints[0]["labels"] == ["RR-mixed-mh"]
        assert endpoints[0]["message"] is None
        assert endpoints[1]["labels"] == []
        assert bare_site.name in endpoints[1]["message"]
        assert "Site Geometry" in endpoints[1]["remedy"]


@pytest.mark.django_db
class TestRouteEndFlag:
    """One badge summarizes both ends: mismatch beats unverified beats ok."""

    def _route(self, cable, pathway):
        CableSegment.objects.create(cable=cable, pathway=pathway, sequence=1)

    def test_ok_when_both_ends_check_out(self, site, admin_user):
        anchor = Structure.objects.create(name="RR-flag-ok", site=site, geometry=Point(0, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RR-F1",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=anchor,
        )
        cable = build_cable_with_terminations(label="RR-flag-ok-cable", site=site)
        self._route(cable, pathway)
        assert _context(admin_user, cable)["route_end_flag"] == "ok"

    def test_unverified_when_one_end_cannot_be_placed(self, site, bare_site, admin_user):
        anchor = Structure.objects.create(name="RR-flag-un", site=site, geometry=Point(0, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RR-F2",
            pathway_type="conduit",
            path=LineString((0, 0), (100, 0), srid=SRID),
            start_structure=anchor,
        )
        cable = build_cable_with_terminations(label="RR-flag-un-cable", site=site, site_b=bare_site)
        self._route(cable, pathway)
        assert _context(admin_user, cable)["route_end_flag"] == "unverified"

    def test_mismatch_beats_unverified(self, site, bare_site, admin_user):
        """The precedence rule's whole purpose: a real problem outranks a shrug."""
        Structure.objects.create(name="RR-flag-mm-anchor", site=site, geometry=Point(0, 0, srid=SRID))
        elsewhere = Structure.objects.create(name="RR-flag-mm-far", geometry=Point(500, 0, srid=SRID))
        pathway = Pathway.objects.create(
            label="RR-F3",
            pathway_type="conduit",
            path=LineString((500, 0), (600, 0), srid=SRID),
            start_structure=elsewhere,
        )
        cable = build_cable_with_terminations(label="RR-flag-mm-cable", site=site, site_b=bare_site)
        self._route(cable, pathway)
        # A end resolves but the route starts somewhere else (mismatch); the B
        # end is not in the plant at all (unverified).
        from netbox_pathways.routing import validate_cable_route

        assert validate_cable_route(cable.pk)["ends"] == {"a": "mismatch", "b": "unverified"}
        assert _context(admin_user, cable)["route_end_flag"] == "mismatch"
