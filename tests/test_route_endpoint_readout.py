"""The Route tab states where each cable end sits, or why it cannot tell."""

import pytest
from django.contrib.gis.geos import Point
from django.test import RequestFactory

from netbox_pathways.geo import get_srid
from netbox_pathways.models import Structure
from netbox_pathways.views import CableRouteView
from tests.conftest import build_cable_with_terminations

SRID = get_srid()


@pytest.fixture
def site(db):
    from dcim.models import Site

    return Site.objects.create(name="RR-site", slug="rr-site")


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
